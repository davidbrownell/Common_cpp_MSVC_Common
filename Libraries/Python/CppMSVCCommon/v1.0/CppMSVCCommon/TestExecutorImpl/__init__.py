# ----------------------------------------------------------------------
# |
# |  __init__.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2019-04-25 09:11:49
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2019
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the TestExecutorImpl object"""

import os

import CommonEnvironment
from CommonEnvironment import Interface
from CommonEnvironment.Shell.All import CurrentShell

from CppCommon.TestExecutorImpl import TestExecutorImpl as TestExecutorImplBase
from CppMSVCCommon.TestExecutorImpl.CodeCoverageExecutor import CodeCoverageExecutor as MSVCCodeCoverageExecutor

# ----------------------------------------------------------------------
_script_fullpath                            = CommonEnvironment.ThisFullpath()
_script_dir, _script_name                   = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
class TestExecutorImpl(TestExecutorImplBase):
    # ----------------------------------------------------------------------
    # |  Methods
    @staticmethod
    @Interface.override
    def ValidateEnvironment():
        if CurrentShell.CategoryName != "Windows":
            return "The '{}' test executor is only available on Windows".format(cls.Name)

    # ----------------------------------------------------------------------
    @staticmethod
    @Interface.override
    def IsSupportedCompiler(compiler):
        return compiler.Name in ["CMake"]

    # ----------------------------------------------------------------------
    _CodeCoverageExecutor                   = Interface.DerivedProperty(MSVCCodeCoverageExecutor)
