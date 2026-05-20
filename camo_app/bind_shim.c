#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <dlfcn.h>
#include <string.h>

typedef int (*connect_t)(int, const struct sockaddr *, socklen_t);

int connect(int sockfd, const struct sockaddr *addr, socklen_t addrlen) {
    static connect_t original_connect = NULL;
    if (!original_connect) {
        original_connect = (connect_t)dlsym(RTLD_NEXT, "connect");
    }

    if (addr && addr->sa_family == AF_INET) {
        char *bind_addr = getenv("BIND_ADDR");
        if (bind_addr && strlen(bind_addr) > 0 && strcmp(bind_addr, "default") != 0) {
            struct sockaddr_in local_addr;
            memset(&local_addr, 0, sizeof(local_addr));
            local_addr.sin_family = AF_INET;
            local_addr.sin_port = 0; // Let the kernel choose a free port
            
            if (inet_pton(AF_INET, bind_addr, &local_addr.sin_addr) == 1) {
                // Bind the socket to the chosen interface IP.
                // We ignore failures so it falls back gracefully if the IP is offline.
                bind(sockfd, (struct sockaddr *)&local_addr, sizeof(local_addr));
            }
        }
    }

    return original_connect(sockfd, addr, addrlen);
}
