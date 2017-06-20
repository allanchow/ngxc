#!/bin/bash
CFLAGS="-I/build/BUILDROOT/vm/include -I/build/BUILDROOT/vm/include/luajit"
LDFLAGS="-L/build/BUILDROOT/vm/lib -L/build/BUILDROOT/vm/lib/luajit -Wl,-rpath=/build/BUILDROOT/vm/lib"
LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:/build/BUILDROOT/vm/lib"

pushd /build/kyoto/kyotocabinet
./configure --enable-lzo --enable-lzma --enable-static --prefix=/build/BUILDROOT/vm CPPFLAGS="${CFLAGS}" CFLAGS="${CFLAGS}" LDFLAGS="${LDFLAGS}"
if [[ $? == 0 ]]; then
make clean
make uninstall
make -j4
make install-strip
fi
popd

pushd /build/kyoto/kyototycoon
#./configure --enable-lua --enable-sec-openssl --with-kc=/build/BUILDROOT/vm --with-lua=/build/BUILDROOT/vm --prefix=/build/BUILDROOT/vm --enable-static --disable-shared CPPFLAGS=${CFLAGS} CFLAGS=${CFLAGS} LDFLAGS=${LDFLAGS}
#./configure --enable-lua --enable-sec-openssl --enable-static --with-kc=/build/BUILDROOT/vm --with-lua=/build/BUILDROOT/vm --prefix=/build/BUILDROOT/vm CPPFLAGS="${CFLAGS}" CFLAGS="${CFLAGS}" LDFLAGS="${LDFLAGS}"
./configure --enable-lua --enable-static --with-kc=/build/BUILDROOT/vm --with-lua=/build/BUILDROOT/vm --prefix=/build/BUILDROOT/vm CPPFLAGS="${CFLAGS}" CFLAGS="${CFLAGS}" LDFLAGS="${LDFLAGS}"
if [[ $? == 0 ]]; then
make clean
make uninstall
make -j4
make install-strip
fi
popd
