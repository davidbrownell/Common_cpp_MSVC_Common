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

if "%CC%" NEQ "clang-cl" (
    echo Clang is not enabled.
    goto :EOF
)

set DEVELOPMENT_ENVIRONMENT_CPP_COMPILER_NAME=%_PREV_DEVELOPMENT_ENVIRONMENT_CPP_COMPILER_NAME%
set _PREV_DEVELOPMENT_ENVIRONMENT_CPP_COMPILER_NAME=

set CFLAGS=
set CXXFLAGS=

set CC=cl
set CXX=cl

echo.
echo The compiler has been set to '%DEVELOPMENT_ENVIRONMENT_CPP_COMPILER_NAME%'.
echo.
