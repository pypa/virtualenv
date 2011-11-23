function global:deactivate($nondestructive) {
    if (Test-Path Env:_OLD_VIRTUAL_PATH) {
        $Env:Path = $Env:_OLD_VIRTUAL_PATH;
        Remove-Item Env:_OLD_VIRTUAL_PATH;
    }

    if (Test-Path Env:_OLD_VIRTUAL_PYTHONHOME) {
        if ($Env:_OLD_VIRTUAL_PYTHONHOME -ne 'NONE') {
            $Env:PYTHONHOME = $Env:_OLD_VIRTUAL_PYTHONHOME;
        }
        else {
            Remove-Item Env:PYTHONHOME;
        }
        Remove-Item Env:_OLD_VIRTUAL_PYTHONHOME;
    }

    if (Test-Path Function:_OLD_VIRTUAL_PROMPT) {
        Set-Content Function:Prompt (Get-Content Function:_OLD_VIRTUAL_PROMPT);
        Remove-Item Function:_OLD_VIRTUAL_PROMPT;
    }

    if (-not $nondestructive) {
        Remove-Item Function:deactivate;
    }
}

deactivate $True;

$Env:VIRTUAL_ENV = "__VIRTUAL_ENV__";

$Env:_OLD_VIRTUAL_PATH = $Env:PATH;
$Env:PATH = "$Env:VIRTUAL_ENV\__BIN_NAME__;$Env:PATH";

if (Test-Path Env:PYTHONHOME) {
    $Env:_OLD_VIRTUAL_PYTHONHOME = $Env:PYTHONHOME
    Remove-Item Env:PYTHONHOME
}

function global:_OLD_VIRTUAL_PROMPT {};
Set-Content Function:_OLD_VIRTUAL_PROMPT (Get-Content Function:Prompt);
Set-Content Function:prompt { "($Env:VIRTUAL_ENV) $(_OLD_VIRTUAL_PROMPT)"; };
