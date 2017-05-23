CFLAGS=-O3 -fPIC -flto -I/usr/include/python2.7 -fomit-frame-pointer 

all: fastbismuth.exe fastminer.so

fastbismuth.exe: fastmark.c
	$(CC) -DFASTMARK_MAIN $(CFLAGS) -o $@ $< -lcrypto

fastminer.c: fastminer.pyx
	cython fastminer.pyx

fastminer.so: fastminer.c
	$(CC) -pthread -shared $(CFLAGS) fastmark.c -o $@ $< `pkg-config python --cflags --libs` -lcrypto
