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

import datetime
import os
import textwrap
import threading
import time

from collections import OrderedDict

import six

import CommonEnvironment
from CommonEnvironment import Interface
from CommonEnvironment.Shell.All import CurrentShell
from CommonEnvironment import StringHelpers
from CommonEnvironment import TaskPool

from CommonEnvironment.TestExecutorImpl import TestExecutorImpl as TestExecutorImplBase

from CppCommon import CodeCoverageFilter

from CppClangCommon.CodeCoverageExecutor import CodeCoverageExecutor as ClangCodeCoverageExecutor
from CppMSVCCommon.TestExecutorImpl.CodeCoverageExecutor import CodeCoverageExecutor as MSVCCodeCoverageExecutor

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

        if os.getenv("CXX") == "clang-cl":
            code_coverage_executor = ClangCodeCoverageExecutor()
        else:
            code_coverage_executor = MSVCCodeCoverageExecutor()

        # ----------------------------------------------------------------------
        def Impl():
            # Instrument the binaries
            on_status_update("Instrumenting Binaries")

            # ----------------------------------------------------------------------
            def Invoke(task_index, output_stream):
                output_filename = context["output_filenames"][task_index]
                return code_coverage_executor.PreprocessBinary(output_filename, output_stream)

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
            coverage_output_filename = os.path.join(context["output_dir"], code_coverage_executor.DefaultFileName)

            on_status_update("Starting Coverage Monitor")

            sink = six.moves.StringIO()
            execute_result.CoverageResult = code_coverage_executor.StartCoverage(coverage_output_filename, sink)
            coverage_output["Starting Coverage Monitor"] = sink.getvalue()

            if execute_result.CoverageResult != 0:
                return

            # Execute the test(s)
            on_status_update("Testing")

            test_start_time = time.time()

            sink = six.moves.StringIO()
            execute_result.TestResult = code_coverage_executor.Execute(command_line, sink)
            execute_result.TestOutput = sink.getvalue()

            execute_result.TestTime = datetime.timedelta(
                seconds=(time.time() - test_start_time),
            )

            if execute_result.TestResult != 0:
                return

            # Stop code coverage monitoring and extract the results
            on_status_update("Stopping Coverage Monitor")

            sink = six.moves.StringIO()
            execute_result.CoverageResult = code_coverage_executor.StopCoverage(sink)
            coverage_output["Stopping Coverage Monitor"] = sink.getvalue()

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

            # ----------------------------------------------------------------------
            def Invoke(task_index, output_stream):
                output_filename = context["output_filenames"][task_index]

                # This is a filename that can be used to specify includes and excludes. Note that this
                # does not correspond to an actual file, as we don't have that information available.
                mock_filter_filename = os.path.join(
                    context["input"],
                    os.path.splitext(os.path.basename(output_filename))[0],
                )

                includes, excludes = CodeCoverageFilter.GetFilters(mock_filter_filename)

                covered, not_covered = code_coverage_executor.ExtractCoverageInfo(
                    coverage_output_filename,
                    output_filename,
                    includes,
                    excludes,
                    output_stream,
                )
                
                all_results[task_index] = (covered, not_covered)

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

            for output_name, (covered, not_covered) in zip(output_names, all_results):
                total_covered += covered
                total_not_covered += not_covered
                
                result_blocks = covered + not_covered
                
                all_percentages[output_name] = (
                    (float(covered) / result_blocks if result_blocks else 0.0) * 100.0,
                    "{} of {} {} covered".format(covered, result_blocks, code_coverage_executor.Units),
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
