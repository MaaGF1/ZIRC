<#
.SYNOPSIS
    Unified Master Build Script for ZIRC.
.EXAMPLE
    .\build.ps1 -Cpp -Mode Release
    .\build.ps1 -Python
#>

param (
    [switch]$Cpp,
    [switch]$Python,
    [ValidateSet("debug", "release")]
    [string]$Mode = "release"
)

$ErrorActionPreference = "Stop"
$SrcDir = $PSScriptRoot

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "[*] ZIRC Unified Build System" -ForegroundColor Cyan
Write-Host "========================================="

# Step 1: Ensure offsets.json is generated (Single Source of Truth)
Write-Host "[*] Step 1: Generating common offsets map..." -ForegroundColor Yellow
$PythonExe = "python"
$GenScript = Join-Path $SrcDir "common\gen_offsets.py"
& $PythonExe $GenScript

if ($LASTEXITCODE -ne 0) {
    Write-Error "[-] Failed to generate offsets."
    exit 1
}

# Step 2: Build C++ Target
if ($Cpp) {
    Write-Host "`n[*] Step 2a: Building C++ Target (Mode: $Mode)..." -ForegroundColor Yellow
    
    # Locate MSVC for SCons
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path $vswhere) {
        $vsPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        if (-not [string]::IsNullOrEmpty($vsPath)) {
            $vcvars = Join-Path $vsPath "VC\Auxiliary\Build\vcvars64.bat"
            if (Test-Path $vcvars) {
                Write-Host "[+] Found MSVC Env: $vcvars" -ForegroundColor Green
                Push-Location (Join-Path $SrcDir "cpp")
                $cmd = "`"$vcvars`" && scons mode=$Mode"
                cmd.exe /c $cmd
                Pop-Location
            } else { Write-Warning "[-] vcvars64.bat not found." }
        }
    } else { Write-Warning "[-] vswhere.exe not found. SCons might fail if environment is not set." }
}

# Step 3: Build Python Target
if ($Python) {
    Write-Host "`n[*] Step 2b: Building Python Target..." -ForegroundColor Yellow
    Push-Location (Join-Path $SrcDir "python")
    & $PythonExe build_py.py
    Pop-Location
}

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "[+] All tasks finished successfully!" -ForegroundColor Green