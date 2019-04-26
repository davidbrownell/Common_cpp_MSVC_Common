@echo off
REM ----------------------------------------------------------------------
REM |
REM |  enable_clang.cmd
REM |
REM |  David Brownell <db@DavidBrownell.com>
REM |      2019-04-12 16:06:32
REM |
REM ----------------------------------------------------------------------
REM |
REM |  Copyright David Brownell 2019
REM |  Distributed under the Boost Software License, Version 1.0. See
REM |  accompanying file LICENSE_1_0.txt or copy at
REM |  http://www.boost.org/LICENSE_1_0.txt.
REM |
REM ----------------------------------------------------------------------

if "%CC%"=="clang-cl" (
    echo Clang is already enabled.
    goto :EOF
)

set _PREV_DEVELOPMENT_ENVIRONMENT_CPP_COMPILER_NAME=%DEVELOPMENT_ENVIRONMENT_CPP_COMPILER_NAME%
set DEVELOPMENT_ENVIRONMENT_CPP_COMPILER_NAME=Clang-8

if "%DEVELOPMENT_ENVIRONMENT_CPP_ARCHITECTURE%"=="x86" (
    set CFLAGS=-m32
    set CXXFLAGS=-m32
)

set CC=clang-cl
set CXX=clang-cl

echo.
echo The compiler has been set to '%DEVELOPMENT_ENVIRONMENT_CPP_COMPILER_NAME%'.
echo.
