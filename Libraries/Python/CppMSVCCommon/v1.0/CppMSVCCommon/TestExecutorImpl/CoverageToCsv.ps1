# Usage
#   %SystemRoot%\syswow64\WindowsPowerShell\v1.0\powershell.exe -ExecutionPolicy Bypass -NoProfile -File CoverageToCsv.ps1

param(
    [Parameter(Mandatory=$true)]
    [string]
    $coverage_filename,
    [string]
    $module_name
)
    $coverage_filename = Resolve-Path -Path "$coverage_filename"
    $coverage_dirname = Split-Path -Path "$coverage_filename" -Parent
 
    Add-Type -Path "${env:DevEnvDir}Extensions\TestPlatform\Microsoft.VisualStudio.Coverage.Analysis.dll"

    $executable_paths = New-Object "System.Collections.Generic.List[String]"
    $symbol_paths = New-Object "System.Collections.Generic.List[String]"
    $symbol_paths.Add($coverage_dirname)

    $ci = [Microsoft.VisualStudio.Coverage.Analysis.CoverageInfo]::CreateFromFile($coverage_filename, $executable_paths, $symbol_paths)
    $data = $ci.BuildDataSet()

    ForEach($module in $data.Module) {
        if(!$module_name -or $module_name -eq $module.ModuleName) {
            ForEach($namespace in $module.GetNamespaceTableRows()) {
                ForEach($class in $namespace.GetClassRows()) {
                    ForEach($method in $class.GetMethodRows()) {
                        Write-Host "`"$module_name`",`"$($method.MethodName)`",$($method.LinesCovered),$($method.LinesPartiallyCovered),$($method.LinesNotCovered),$($method.BlocksCovered),$($method.BlocksNotCovered)"
                    }
                }
            }
        }
    }
