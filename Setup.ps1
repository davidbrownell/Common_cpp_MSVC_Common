# ----------------------------------------------------------------------
# |  
# |  Setup.ps1
# |  
# |  Michael Sharp <ms@MichaelGSharp.com>
# |      2018-06-07 11:21:37
# |  
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# |  
# |  Run as:
# |     Setup.ps1 [/debug] [/verbose] [/configuration=<config_name>]*
# |  
# ----------------------------------------------------------------------

$env:DEVELOPMENT_ENVIRONMENT_USE_WINDOWS_POWERSHELL=1

function ExitScript {
    Remove-Item "NULL" -ErrorAction SilentlyContinue
    exit
}

if ([string]::IsNullOrEmpty($env:DEVELOPMENT_ENVIRONMENT_FUNDAMENTAL)) {
    Write-Error `
(@"
 
 
Please run Activate.ps1 within a repository before running this script. It may be necessary to Setup and Activate the Common_Environment repository before setting up this one.
 
"@)

    ExitScript
}

pushd "$PSScriptRoot"
Invoke-Expression "$env:DEVELOPMENT_ENVIRONMENT_FUNDAMENTAL\RepositoryBootstrap\Impl\Setup.cmd $args"
popd

ExitScript
