Compiling and Running
---------------------

Use `cmake`:
```sh
cmake -Bbuild
cmake --build build
./build/lsh
```

Has been tested on:
- Ubuntu 22.04
- Devuan Chimaera 4.0 (StuDAT)
- macOS 12.x / 13.x (apple silicon)

Compiling with `clang`
----------------------

If you want to use `clang`, there is a toolchain file you can use:
```sh
cmake -Bbuild --toolchain clang.cmake
cmake --build build
./build/lsh
```
