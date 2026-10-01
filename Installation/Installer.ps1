param([ValidateSet('Complete','Application')][string]$Mode='Complete')
$ErrorActionPreference = 'Stop'
$vodRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $vodRoot
$env:PYTHONUTF8 = '1'
$env:PIP_CACHE_DIR = Join-Path $vodRoot '.cache\pip'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Assert-InWorkspace([string]$Path) {
    $resolved = [IO.Path]::GetFullPath($Path)
    if (!$resolved.StartsWith($vodRoot + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Dossier hors de l''application.' }
    return $resolved
}

function Test-Python([string]$Executable) {
    if (!(Test-Path -LiteralPath $Executable -PathType Leaf)) { return $false }
    try {
        & $Executable -c 'import sys,venv,ensurepip; assert sys.version_info[:2] == (3,12) and sys.maxsize > 2**32' 2>$null
        return $LASTEXITCODE -eq 0
    } catch { return $false }
}

function Get-Python {
    $candidates = @((Join-Path $vodRoot '.venv\Scripts\python.exe'),
                    (Join-Path $vodRoot 'tools\python\tools\python.exe'),
                    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'))
    foreach ($candidate in $candidates) { if (Test-Python $candidate) { return $candidate } }
    foreach ($name in @('py.exe','python.exe')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) {
            try { $found = if ($name -eq 'py.exe') { & $command.Source -3.12 -c 'import sys; print(sys.executable)' 2>$null } else { & $command.Source -c 'import sys; print(sys.executable)' 2>$null } } catch { continue }
            if ($LASTEXITCODE -eq 0 -and $found) { $candidates += [string]$found }
        }
    }
    foreach ($candidate in $candidates) { if (Test-Python $candidate) { return $candidate } }
    Write-Host 'Téléchargement de Python 3.12 x64 (distribution officielle NuGet)...'
    $versions = (Invoke-RestMethod 'https://api.nuget.org/v3-flatcontainer/python/index.json').versions
    $version = $versions | Where-Object { $_ -match '^3\.12\.\d+$' } | Sort-Object { [Version]$_ } -Descending | Select-Object -First 1
    if (!$version) { throw 'Python 3.12 indisponible sur NuGet.' }
    $downloads = Join-Path $vodRoot '.cache\downloads'
    New-Item -ItemType Directory -Force -Path $downloads | Out-Null
    $archive = Join-Path $downloads 'python.zip'
    Invoke-WebRequest -UseBasicParsing -Uri "https://api.nuget.org/v3-flatcontainer/python/$version/python.$version.nupkg" -OutFile $archive
    $tools = Join-Path $vodRoot 'tools'
    New-Item -ItemType Directory -Force -Path $tools | Out-Null
    $stage = Assert-InWorkspace (Join-Path $tools ('python_install_' + [Guid]::NewGuid().ToString('N')))
    Expand-Archive -LiteralPath $archive -DestinationPath $stage
    $runtime = Join-Path $stage 'tools\python.exe'
    if (!(Test-Python $runtime)) { throw 'Le Python téléchargé ne démarre pas.' }
    $target = Assert-InWorkspace (Join-Path $tools 'python')
    if (Test-Path -LiteralPath $target) {
        $backup = Assert-InWorkspace (Join-Path $tools ('python_incomplet_' + [Guid]::NewGuid().ToString('N')))
        Move-Item -LiteralPath $target -Destination $backup
    }
    Move-Item -LiteralPath $stage -Destination $target
    return (Join-Path $target 'tools\python.exe')
}

function Test-WebView2 {
    $keys = @('HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
              'HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
              'HKCU:\Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}')
    foreach ($key in $keys) {
        $value = (Get-ItemProperty -LiteralPath $key -Name pv -ErrorAction SilentlyContinue).pv
        if ($value -and $value -ne '0.0.0.0') { return $true }
    }
    return $false
}

Start-Transcript -Path (Join-Path $PSScriptRoot 'installation.log') -Append | Out-Null
try {
    if (![Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { throw 'Cette version nécessite Windows Intel/AMD 64 bits.' }
    Write-Host '1/5 - Préparation de Python et de l''environnement de l''application...'
    $python = Get-Python
    $venv = Join-Path $vodRoot '.venv\Scripts\python.exe'
    if (!(Test-Python $venv)) {
        $envFolder = Assert-InWorkspace (Join-Path $vodRoot '.venv')
        if (Test-Path -LiteralPath $envFolder) {
            $backup = Assert-InWorkspace (Join-Path $vodRoot ('.venv_incomplet_' + [Guid]::NewGuid().ToString('N')))
            Move-Item -LiteralPath $envFolder -Destination $backup
        }
        & $python -m venv $envFolder
        if ($LASTEXITCODE -ne 0) { throw 'Création de l''environnement Python impossible.' }
    }
    Write-Host '2/5 - Installation des dépendances de l''application...'
    & $venv -m pip install --disable-pip-version-check -r (Join-Path $vodRoot 'requirements.txt') -r (Join-Path $vodRoot 'requirements-build.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Installation des bibliothèques impossible.' }
    Write-Host '3/5 - Vérification de FFmpeg / FFprobe et de la fenêtre Windows...'
    & $venv (Join-Path $vodRoot 'setup_tools.py')
    if ($LASTEXITCODE -ne 0) { throw 'Installation de FFmpeg impossible.' }
    if (!(Test-WebView2)) {
        Write-Host 'Installation du composant graphique Microsoft WebView2...'
        $installer = Join-Path $vodRoot '.cache\downloads\MicrosoftEdgeWebview2Setup.exe'
        New-Item -ItemType Directory -Force -Path (Split-Path $installer -Parent) | Out-Null
        Invoke-WebRequest -UseBasicParsing -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $installer
        $signature = Get-AuthenticodeSignature -LiteralPath $installer
        if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') { throw 'Signature Microsoft du composant graphique invalide.' }
        $process = Start-Process -FilePath $installer -ArgumentList '/silent','/install' -WindowStyle Hidden -PassThru -Wait
        if (!(Test-WebView2)) { throw "WebView2 indisponible (code $($process.ExitCode))." }
    }
    Write-Host '4/5 - Création de VOD Atelier.exe...'
    & $venv (Join-Path $vodRoot 'build_desktop.py')
    if ($LASTEXITCODE -ne 0) { throw 'Création du fichier EXE impossible.' }
    if ($Mode -eq 'Complete') {
        Write-Host '5/5 - Préparation des IA locales : plusieurs Go, uniquement la première fois...'
        & $venv (Join-Path $vodRoot 'setup_ai.py')
        if ($LASTEXITCODE -ne 0) { throw 'Préparation IA incomplète. Relance Installer.cmd pour reprendre.' }
    } else {
        Write-Host '5/5 - Application prête. Les modèles peuvent être préparés depuis son interface.'
    }
    Write-Host 'Terminé : double-clique sur VOD Atelier.exe dans le dossier de l''application.'
    Stop-Transcript | Out-Null
    exit 0
} catch {
    Write-Host ('ERREUR : ' + $_.Exception.Message) -ForegroundColor Red
    Stop-Transcript | Out-Null
    exit 1
}
