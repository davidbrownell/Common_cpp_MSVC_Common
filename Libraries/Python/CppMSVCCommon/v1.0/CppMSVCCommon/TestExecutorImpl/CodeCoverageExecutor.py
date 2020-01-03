# ----------------------------------------------------------------------
# |
# |  CodeCoverageExecutor.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2019-04-25 13:15:53
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2019-20
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the CodeCoverageExecutor object"""

import csv
from fnmatch import fnmatch
import os
import subprocess

import CommonEnvironment
from CommonEnvironment.CallOnExit import CallOnExit
from CommonEnvironment import FileSystem
from CommonEnvironment import Interface
from CommonEnvironment import Process
from CommonEnvironment.Shell.All import CurrentShell

from CppCommon.CodeCoverageExecutor import CodeCoverageExecutor as CodeCoverageExecutorBase

# ----------------------------------------------------------------------
_script_fullpath                            = CommonEnvironment.ThisFullpath()
_script_dir, _script_name                   = os.path.split(_script_fullpath)
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
@Interface.staticderived
class CodeCoverageExecutor(CodeCoverageExecutorBase):
    """Extracts code coverage using MSVC performance tools"""

    # ----------------------------------------------------------------------
    # |  Properties
    DefaultFileName                         = Interface.DerivedProperty("code.coverage")
    Units                                   = Interface.DerivedProperty("blocks")

    # ----------------------------------------------------------------------
    # |  Methods
    @staticmethod
    @Interface.override
    def PreprocessBinary(binary_filename, output_stream):
        FileSystem.RemoveFile("{}.orig".format(binary_filename))
        return Process.Execute('vsinstr "{}" /COVERAGE'.format(binary_filename), output_stream)

    # ----------------------------------------------------------------------
    @classmethod
    @Interface.override
    def StartCoverage(cls, coverage_filename, output_stream):
        # Shutdown any existing monitors
        cls.StopCoverage(output_stream)

        result, output = _ProcessExecuteWorkaround(
            'VSPerfCmd.exe /WAITSTART /START:COVERAGE "/OUTPUT:{}"'.format(
                coverage_filename,
            ),
        )
        output_stream.write(output)

        return result

    # ----------------------------------------------------------------------
    @staticmethod
    @Interface.override
    def StopCoverage(output_stream):
        return Process.Execute("VSPerfCmd.exe /SHUTDOWN", output_stream)

    # ----------------------------------------------------------------------
    @staticmethod
    @Interface.override
    def ExtractCoverageInfo(coverage_filename, binary_filename, includes, excludes, output_stream):
        if excludes:
            excludes_func = lambda method_name: any(fnmatch(method_name, exclude) for exclude in excludes)
        else:
            excludes_func = lambda method_name: False

        if includes:
            includes_func = lambda method_name: any(fnmatch(method_name, include) for include in includes)
        else:
            includes_func = lambda method_name: True

        # ----------------------------------------------------------------------
        def ShouldInclude(method_name):
            return not excludes_func(method_name) and includes_func(method_name)

        # ----------------------------------------------------------------------

        temp_filename = CurrentShell.CreateTempFilename()

        command_line = '"{powershell}" -ExecutionPolicy Bypass -NoProfile -File "{filename}" "{coverage}" "{module}" > "{temp_filename}" 2>&1'.format(
            powershell=r"{}\syswow64\WindowsPowerShell\v1.0\powershell.exe".format(
                os.getenv("SystemRoot"),
            ),
            filename=os.path.join(_script_dir, "CoverageToCsv.ps1"),
            coverage=coverage_filename,
            module=os.path.basename(binary_filename),
            temp_filename=temp_filename,
        )

        result = Process.Execute(command_line, output_stream)
        if result != 0:
            return result

        with CallOnExit(lambda: FileSystem.RemoveFile(temp_filename)):
            covered = 0
            not_covered = 0

            with open(temp_filename, "r") as input:
                reader = csv.reader(input)

                for row in reader:
                    if not isinstance(row, (tuple, list)):
                        raise Exception(row)
                    if len(row) == 1:
                        raise Exception(row[0])

                    method_name = row[1]
                    if not ShouldInclude(method_name):
                        continue

                    covered += int(row[-2])
                    not_covered += int(row[-1])

            return covered, not_covered


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _ProcessExecuteWorkaround(command_line):
    # I haven't been able to figure out what is causing this, but it appears that VSPerfCmd.exe
    # isn't sending an EOF before terminating during startup. This causes problems for subprocess-
    # based means of forking processes and ends up hanging forever. To work around this, use
    # subprocess.call, which doesn't use standard streams for input and output.
    #
    # Unfortunately, there isn't an easy way to capture the output from subprocess.call, so
    # invoke the command with output redirected to a file, then extract the content from the
    # file itself.
    #
    # This is all a great big hack.

    temp_filename = CurrentShell.CreateTempFilename("._ProcessExecuteWorkaround.output")

    command_line += ' > "{}" 2>&1'.format(temp_filename)

    result = subprocess.call(
        command_line,
        shell=True,
    )

    assert os.path.isfile(temp_filename), temp_filename
    with open(temp_filename) as f:
        output = f.read()

    # For some reason, this file is still in use when we attempt to delete it here.
    # For now, don't delete it as it should be pretty small.
    #
    # FileSystem.RemoveFile(temp_filename)

    return result, output
