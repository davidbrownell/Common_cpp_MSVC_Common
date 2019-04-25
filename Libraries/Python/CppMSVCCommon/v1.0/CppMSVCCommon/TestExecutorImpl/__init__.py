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

import csv
import datetime
from fnmatch import fnmatch
import os
import subprocess
import textwrap
import threading
import time

from collections import OrderedDict, namedtuple

import six

import CommonEnvironment
from CommonEnvironment.CallOnExit import CallOnExit
from CommonEnvironment import FileSystem
from CommonEnvironment import Interface
from CommonEnvironment import Process
from CommonEnvironment.Shell.All import CurrentShell
from CommonEnvironment import StringHelpers
from CommonEnvironment import TaskPool

from CommonEnvironment.TestExecutorImpl import TestExecutorImpl as TestExecutorImplBase

from CppCommon import CodeCoverageFilter

# ----------------------------------------------------------------------
_script_fullpath                            = CommonEnvironment.ThisFullpath()
_script_dir, _script_name                   = os.path.split(_script_fullpath)
#  ----------------------------------------------------------------------

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
    @classmethod
    @Interface.override
    def Execute(
        cls,
        on_status_update,
        compiler,
        context,
        command_line,
        includes=None,
        excludes=None,
        verbose=False,
    ):
        execute_result = cls.ExecuteResult(
            test_result=None,
            test_output=None,
            test_time=None,
        )

        coverage_start_time = time.time()
        coverage_output = OrderedDict()

        # ----------------------------------------------------------------------
        def Impl():
            # Instrument the binaries
            on_status_update("Instrumenting Binaries")

            command_line_template = 'vsinstr "{}" /COVERAGE'

            # ----------------------------------------------------------------------
            def Invoke(task_index, output_stream):
                output_filename = context["output_filenames"][task_index]
                if os.path.isfile("{}.orig".format(output_filename)):
                    return 0

                return Process.Execute(command_line_template.format(output_filename), output_stream)

            # ----------------------------------------------------------------------

            sink = six.moves.StringIO()

            execute_result.CoverageResult = TaskPool.Execute(
                [TaskPool.Task(output_filename, Invoke) for output_filename in context["output_filenames"]],
                sink,
                verbose=True,
            )

            coverage_output["Instrumenting Binaries"] = sink.getvalue()

            if execute_result.CoverageResult != 0:
                return

            # Start coverage
            coverage_output_filename = os.path.join(context["output_dir"], "code.coverage")

            on_status_update("Starting Coverage Monitor")

            # Showdown any existing monitors
            Process.Execute("VSPerfCmd.exe /SHUTDOWN")

            # Start a new monitor
            execute_result.CoverageResult, output = _ProcessExecuteWorkaround(
                'VSPerfCmd.exe /WAITSTART /START:COVERAGE "/OUTPUT:{}"'.format(
                    coverage_output_filename,
                ),
            )
            coverage_output["Starting Coverage Monitor"] = output

            if execute_result.CoverageResult != 0:
                return

            # Stop code coverage monitoring once the test is complete

            # ----------------------------------------------------------------------
            def StopCoverageMonitoring():
                on_status_update("Stopping Coverage Monitor")

                execute_result.CoverageResult, output = Process.Execute("VSPerfCmd.exe /SHUTDOWN")
                coverage_output["Stopping Coverage Monitor"] = output

            # ----------------------------------------------------------------------

            with CallOnExit(StopCoverageMonitoring):
                # Execute the test(s)
                on_status_update("Testing")

                test_start_time = time.time()

                execute_result.TestResult, execute_result.TestOutput = Process.Execute(command_line)
                execute_result.TestTime = datetime.timedelta(
                    seconds=(time.time() - test_start_time),
                )

                if execute_result.TestResult != 0:
                    return

            if execute_result.CoverageResult != 0:
                return

            # Process the results
            output_names = [os.path.basename(output_filename) for output_filename in context["output_filenames"]]
            all_results = [None] * len(output_names)

            nonlocals = CommonEnvironment.Nonlocals(
                remaining=len(output_names),
            )
            nonlocals_lock = threading.Lock()

            status_template = "Extracting Coverage Results ({} remaining)"

            on_status_update(status_template.format(nonlocals.remaining))

            # The coverage file generated has content that can be extracted by .NET Assemblies.
            # Invoke powershell (which can interface with .NET) to do this.
            command_line_template = '"{powershell}" -ExecutionPolicy Bypass -NoProfile -File "{filename}" "{coverage}" "{{module}}" > "{{temp_filename}}" 2>&1'.format(
                powershell=r"{}\syswow64\WindowsPowerShell\v1.0\powershell.exe".format(
                    os.getenv("SystemRoot"),
                ),
                filename=os.path.join(_script_dir, "CoverageToCsv.ps1"),
                coverage=coverage_output_filename,
            )

            # ----------------------------------------------------------------------
            ModuleResult = namedtuple("ModuleResult", ["covered", "not_covered"])

            # ----------------------------------------------------------------------
            def Invoke(task_index, output_stream):
                temp_filename = CurrentShell.CreateTempFilename()

                output_filename = context["output_filenames"][task_index]

                result = Process.Execute(
                    command_line_template.format(
                        module=os.path.basename(output_filename),
                        temp_filename=temp_filename,
                    ),
                    output_stream,
                )

                if result != 0:
                    return result

                with CallOnExit(lambda: FileSystem.RemoveFile(temp_filename)):
                    # This is a filename that can be used to specify includes and excludes. Note that this
                    # does not correspond to an actual file, as we don't have that information available.
                    mock_filter_filename = os.path.join(
                        context["input"],
                        os.path.splitext(os.path.basename(output_filename))[0],
                    )

                    includes, excludes = CodeCoverageFilter.GetFilters(mock_filter_filename)

                    # ----------------------------------------------------------------------
                    def Include(method_name):
                        if excludes and any(fnmatch(method_name, exclude) for exclude in excludes):
                            return False

                        if includes and not any(fnmatch(method_name, include) for include in includes):
                            return False

                        return True

                    # ----------------------------------------------------------------------

                    covered = 0
                    not_covered = 0

                    with open(temp_filename, "r") as input:
                        reader = csv.reader(input)

                        for row in reader:
                            if not isinstance(row, (tuple, list)):
                                raise Exception(row)

                            method_name = row[1]
                            if not Include(method_name):
                                continue

                            covered += int(row[-2])
                            not_covered += int(row[-1])

                    all_results[task_index] = ModuleResult(covered, not_covered)

                    with nonlocals_lock:
                        nonlocals.remaining -= 1
                        on_status_update(status_template.format(nonlocals.remaining))

                return 0

            # ----------------------------------------------------------------------

            sink = six.moves.StringIO()

            execute_result.CoverageResult = TaskPool.Execute(
                [TaskPool.Task(output_name, Invoke) for output_name in output_names],
                sink,
                verbose=True,
            )

            coverage_output["Extracting Coverage Results"] = sink.getvalue()

            if execute_result.CoverageResult != 0:
                return

            # Concatenate the results
            on_status_update("Finalizing Results")

            total_covered = 0
            total_not_covered = 0

            all_percentages = OrderedDict()

            for output_name, results in zip(output_names, all_results):
                total_covered += results.covered
                total_not_covered += results.not_covered
                
                result_blocks = results.covered + results.not_covered
                
                all_percentages[output_name] = (
                    (float(results.covered) / result_blocks if result_blocks else 0.0) * 100.0,
                    "{} of {} blocks covered".format(results.covered, result_blocks),
                )

            total_blocks = total_covered + total_not_covered

            execute_result.CoverageDataFilename = coverage_output_filename
            execute_result.CoveragePercentage = (float(total_covered) / total_blocks if total_blocks else 0.0) * 100.0
            execute_result.CoveragePercentages = all_percentages

        # ----------------------------------------------------------------------

        Impl()

        execute_result.CoverageOutput = "".join(
            [
                textwrap.dedent(
                    """\
                    {}
                    {}
                        {}


                    """,
                ).format(header, "-" * len(header), StringHelpers.LeftJustify(content.strip(), 4))
                for header, content in six.iteritems(coverage_output)
            ],
        )

        execute_result.CoverageTime = datetime.timedelta(
            seconds=(time.time() - coverage_start_time),
        )

        # Subtract the time spent testing (if it exists)
        if execute_result.TestTime is not None:
            assert execute_result.CoverageTime >= execute_result.TestTime
            execute_result.CoverageTime -= execute_result.TestTime

            execute_result.TestTime = str(execute_result.TestTime)

        execute_result.CoverageTime = str(execute_result.CoverageTime)

        return execute_result


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
