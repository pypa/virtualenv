# This file must be dot sourced from PoSh; you cannot run it
# directly. Do this: . ./activate.ps1

# FIXME: clean up unused vars.
$script:THIS_PATH = $myinvocation.mycommand.path
$script:BASE_DIR = split-path (resolve-path "$THIS_PATH/..") -Parent
$script:DIR_NAME = split-path $BASE_DIR -Leaf

function global:deactivate ( [switch] $NonDestructive ){

    if ( test-path variable:_OLD_VIRTUAL_PATH ) {
        $env:PATH = $variable:_OLD_VIRTUAL_PATH
        remove-variable "_OLD_VIRTUAL_PATH" -scope global
    }

    if ( test-path function:_old_virtual_prompt ) {
        $function:prompt = $function:_old_virtual_prompt
        remove-item function:\_old_virtual_prompt
    }

    if ($env:VIRTUAL_ENV) {
        $old_env = split-path $env:VIRTUAL_ENV -leaf
        remove-item env:VIRTUAL_ENV -erroraction silentlycontinue
    }

    if ( !$NonDestructive ) {
        # Self destruct!
        remove-item function:deactivate
    }
}

# unset irrelevant variables
deactivate -nondestructive

$VIRTUAL_ENV = $BASE_DIR
$env:VIRTUAL_ENV = $VIRTUAL_ENV

$global:_OLD_VIRTUAL_PATH = $env:PATH
$env:PATH = "$env:VIRTUAL_ENV/Scripts;" + $env:PATH
function global:_old_virtual_prompt { "" }
$function:_old_virtual_prompt = $function:prompt
function global:prompt {
    # Add a prefix to the current prompt, but don't discard it.
    write-host "($(split-path $env:VIRTUAL_ENV -leaf)) " -nonewline
    & $function:_old_virtual_prompt
}

# SIG # Begin signature block
# MIIQiwYJKoZIhvcNAQcCoIIQfDCCEHgCAQExCzAJBgUrDgMCGgUAMGkGCisGAQQB
# gjcCAQSgWzBZMDQGCisGAQQBgjcCAR4wJgIDAQAABBAfzDtgWUsITrck0sYpfvNR
# AgEAAgEAAgEAAgEAAgEAMCEwCQYFKw4DAhoFAAQUS5reBwSg3zOUwhXf2jPChZzf
# yPmggg3AMIIGcDCCBFigAwIBAgIBJDANBgkqhkiG9w0BAQUFADB9MQswCQYDVQQG
# EwJJTDEWMBQGA1UEChMNU3RhcnRDb20gTHRkLjErMCkGA1UECxMiU2VjdXJlIERp
# Z2l0YWwgQ2VydGlmaWNhdGUgU2lnbmluZzEpMCcGA1UEAxMgU3RhcnRDb20gQ2Vy
# dGlmaWNhdGlvbiBBdXRob3JpdHkwHhcNMDcxMDI0MjIwMTQ2WhcNMTcxMDI0MjIw
# MTQ2WjCBjDELMAkGA1UEBhMCSUwxFjAUBgNVBAoTDVN0YXJ0Q29tIEx0ZC4xKzAp
# BgNVBAsTIlNlY3VyZSBEaWdpdGFsIENlcnRpZmljYXRlIFNpZ25pbmcxODA2BgNV
# BAMTL1N0YXJ0Q29tIENsYXNzIDIgUHJpbWFyeSBJbnRlcm1lZGlhdGUgT2JqZWN0
# IENBMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAyiOLIjUemqAbPJ1J
# 0D8MlzgWKbr4fYlbRVjvhHDtfhFN6RQxq0PjTQxRgWzwFQNKJCdU5ftKoM5N4YSj
# Id6ZNavcSa6/McVnhDAQm+8H3HWoD030NVOxbjgD/Ih3HaV3/z9159nnvyxQEckR
# ZfpJB2Kfk6aHqW3JnSvRe+XVZSufDVCe/vtxGSEwKCaNrsLc9pboUoYIC3oyzWoU
# TZ65+c0H4paR8c8eK/mC914mBo6N0dQ512/bkSdaeY9YaQpGtW/h/W/FkbQRT3sC
# pttLVlIjnkuY4r9+zvqhToPjxcfDYEf+XD8VGkAqle8Aa8hQ+M1qGdQjAye8OzbV
# uUOw7wIDAQABo4IB6TCCAeUwDwYDVR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8EBAMC
# AQYwHQYDVR0OBBYEFNBOD0CZbLhLGW87KLjg44gHNKq3MB8GA1UdIwQYMBaAFE4L
# 7xqkQFulF2mHMMo0aEPQQa7yMD0GCCsGAQUFBwEBBDEwLzAtBggrBgEFBQcwAoYh
# aHR0cDovL3d3dy5zdGFydHNzbC5jb20vc2ZzY2EuY3J0MFsGA1UdHwRUMFIwJ6Al
# oCOGIWh0dHA6Ly93d3cuc3RhcnRzc2wuY29tL3Nmc2NhLmNybDAnoCWgI4YhaHR0
# cDovL2NybC5zdGFydHNzbC5jb20vc2ZzY2EuY3JsMIGABgNVHSAEeTB3MHUGCysG
# AQQBgbU3AQIBMGYwLgYIKwYBBQUHAgEWImh0dHA6Ly93d3cuc3RhcnRzc2wuY29t
# L3BvbGljeS5wZGYwNAYIKwYBBQUHAgEWKGh0dHA6Ly93d3cuc3RhcnRzc2wuY29t
# L2ludGVybWVkaWF0ZS5wZGYwEQYJYIZIAYb4QgEBBAQDAgABMFAGCWCGSAGG+EIB
# DQRDFkFTdGFydENvbSBDbGFzcyAyIFByaW1hcnkgSW50ZXJtZWRpYXRlIE9iamVj
# dCBTaWduaW5nIENlcnRpZmljYXRlczANBgkqhkiG9w0BAQUFAAOCAgEAcnMLA3Va
# N4OIE9l4QT5OEtZy5PByBit3oHiqQpgVEQo7DHRsjXD5H/IyTivpMikaaeRxIv95
# baRd4hoUcMwDj4JIjC3WA9FoNFV31SMljEZa66G8RQECdMSSufgfDYu1XQ+cUKxh
# D3EtLGGcFGjjML7EQv2Iol741rEsycXwIXcryxeiMbU2TPi7X3elbwQMc4JFlJ4B
# y9FhBzuZB1DV2sN2irGVbC3G/1+S2doPDjL1CaElwRa/T0qkq2vvPxUgryAoCppU
# FKViw5yoGYC+z1GaesWWiP1eFKAL0wI7IgSvLzU3y1Vp7vsYaxOVBqZtebFTWRHt
# XjCsFrrQBngt0d33QbQRI5mwgzEp7XJ9xu5d6RVWM4TPRUsd+DDZpBHm9mszvi9g
# VFb2ZG7qRRXCSqys4+u/NLBPbXi/m/lU00cODQTlC/euwjk9HQtRrXQ/zqsBJS6U
# J+eLGw1qOfj+HVBl/ZQpfoLk7IoWlRQvRL1s7oirEaqPZUIWY/grXq9r6jDKAp3L
# ZdKQpPOnnogtqlU4f7/kLjEJhrrc98mrOWmVMK/BuFRAfQ5oDUMnVmCzAzLMjKfG
# cVW/iMew41yfhgKbwpfzm3LBr1Zv+pEBgcgW6onRLSAn3XHM0eNtz+AkxH6rRf6B
# 2mYhLEEGLapH8R1AMAo4BbVFOZR5kXcMCwowggdIMIIGMKADAgECAgIDrjANBgkq
# hkiG9w0BAQUFADCBjDELMAkGA1UEBhMCSUwxFjAUBgNVBAoTDVN0YXJ0Q29tIEx0
# ZC4xKzApBgNVBAsTIlNlY3VyZSBEaWdpdGFsIENlcnRpZmljYXRlIFNpZ25pbmcx
# ODA2BgNVBAMTL1N0YXJ0Q29tIENsYXNzIDIgUHJpbWFyeSBJbnRlcm1lZGlhdGUg
# T2JqZWN0IENBMB4XDTExMDcyMzEwMzU1MloXDTEzMDcyMzA4MjcxNFowgZ8xIDAe
# BgNVBA0TFzQ2OTQ0Ny1VdDVPYzBwUFdIeUdodXU1MQswCQYDVQQGEwJVUzEdMBsG
# A1UECBMURGlzdHJpY3Qgb2YgQ29sdW1iaWExEzARBgNVBAcTCldhc2hpbmd0b24x
# GDAWBgNVBAMTD0phc29uIFIuIENvb21iczEgMB4GCSqGSIb3DQEJARYRamFyYWNv
# QGphcmFjby5jb20wggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQDMx+op
# jGsiU1XOIW0j/O7rM8MFln48xLjY1bI0IaWF/IMgibuZNOW/MdKdW5VVeVm7/TDY
# tW51JSlqWnZRnm69aZBp9HaKvx2UhOG3QxQ5Y31i6SkhYGxIcqZL56oi8ZfP+utB
# hNZ7p9Vd07J2bSyV6TLo3l3lYWJXg7dPLa80LsMwyvr3edgv9gfdOe4iu8R3Stuw
# HvKSvVDZiM68AV8j4Sr52rqw2B8+XgI0PjYBeRTTZEpdLBA2+aEV6HdMR18T58MU
# mbS0Rh5Cuzz7cIGjq+3qAPGoKcgLs982uXNCuRZg0ktZx/xHPNxZHlCOTIwXX3jS
# pttFcOoRmyV+SsfdAgMBAAGjggOdMIIDmTAJBgNVHRMEAjAAMA4GA1UdDwEB/wQE
# AwIHgDAuBgNVHSUBAf8EJDAiBggrBgEFBQcDAwYKKwYBBAGCNwIBFQYKKwYBBAGC
# NwoDDTAdBgNVHQ4EFgQUbPWi+/gX3fI+ePdHLuXptAuaWckwHwYDVR0jBBgwFoAU
# 0E4PQJlsuEsZbzsouODjiAc0qrcwggIhBgNVHSAEggIYMIICFDCCAhAGCysGAQQB
# gbU3AQICMIIB/zAuBggrBgEFBQcCARYiaHR0cDovL3d3dy5zdGFydHNzbC5jb20v
# cG9saWN5LnBkZjA0BggrBgEFBQcCARYoaHR0cDovL3d3dy5zdGFydHNzbC5jb20v
# aW50ZXJtZWRpYXRlLnBkZjCB9wYIKwYBBQUHAgIwgeowJxYgU3RhcnRDb20gQ2Vy
# dGlmaWNhdGlvbiBBdXRob3JpdHkwAwIBARqBvlRoaXMgY2VydGlmaWNhdGUgd2Fz
# IGlzc3VlZCBhY2NvcmRpbmcgdG8gdGhlIENsYXNzIDIgVmFsaWRhdGlvbiByZXF1
# aXJlbWVudHMgb2YgdGhlIFN0YXJ0Q29tIENBIHBvbGljeSwgcmVsaWFuY2Ugb25s
# eSBmb3IgdGhlIGludGVuZGVkIHB1cnBvc2UgaW4gY29tcGxpYW5jZSBvZiB0aGUg
# cmVseWluZyBwYXJ0eSBvYmxpZ2F0aW9ucy4wgZwGCCsGAQUFBwICMIGPMCcWIFN0
# YXJ0Q29tIENlcnRpZmljYXRpb24gQXV0aG9yaXR5MAMCAQIaZExpYWJpbGl0eSBh
# bmQgd2FycmFudGllcyBhcmUgbGltaXRlZCEgU2VlIHNlY3Rpb24gIkxlZ2FsIGFu
# ZCBMaW1pdGF0aW9ucyIgb2YgdGhlIFN0YXJ0Q29tIENBIHBvbGljeS4wNgYDVR0f
# BC8wLTAroCmgJ4YlaHR0cDovL2NybC5zdGFydHNzbC5jb20vY3J0YzItY3JsLmNy
# bDCBiQYIKwYBBQUHAQEEfTB7MDcGCCsGAQUFBzABhitodHRwOi8vb2NzcC5zdGFy
# dHNzbC5jb20vc3ViL2NsYXNzMi9jb2RlL2NhMEAGCCsGAQUFBzAChjRodHRwOi8v
# YWlhLnN0YXJ0c3NsLmNvbS9jZXJ0cy9zdWIuY2xhc3MyLmNvZGUuY2EuY3J0MCMG
# A1UdEgQcMBqGGGh0dHA6Ly93d3cuc3RhcnRzc2wuY29tLzANBgkqhkiG9w0BAQUF
# AAOCAQEAjCobx8UN6Nr3cJC8dQ8SiBG6LDcX7LcPoFDdD0oK5AA6JHjQGLyaPxy5
# v20aYeRPyrp4dxQ37ard+D0SQYeYXo4+KoS4RQqgmA6fLkxN/wq3zq3iQZQub+x+
# ZIM58TfsnUZ6RCmagbeg0wnVc/5VTsm+j9EmCjThigeNlcaelKlBotUIOF7ojqRp
# bch8jowSIX5lDMQaEBtU7ZLzcnRUmS9A5ZCBwz7Irs3bbToWHkyNfD57jiIQJGzx
# awE9BW5ubfI+W/8xhwmCxL/bPRQEsMK5PczHIdKx8zu8VqRYSrgetdE6iSdScuwB
# vEb1A6UD2DjWcod2MZNvxEBdeCK4pzGCAjUwggIxAgEBMIGTMIGMMQswCQYDVQQG
# EwJJTDEWMBQGA1UEChMNU3RhcnRDb20gTHRkLjErMCkGA1UECxMiU2VjdXJlIERp
# Z2l0YWwgQ2VydGlmaWNhdGUgU2lnbmluZzE4MDYGA1UEAxMvU3RhcnRDb20gQ2xh
# c3MgMiBQcmltYXJ5IEludGVybWVkaWF0ZSBPYmplY3QgQ0ECAgOuMAkGBSsOAwIa
# BQCgeDAYBgorBgEEAYI3AgEMMQowCKACgAChAoAAMBkGCSqGSIb3DQEJAzEMBgor
# BgEEAYI3AgEEMBwGCisGAQQBgjcCAQsxDjAMBgorBgEEAYI3AgEVMCMGCSqGSIb3
# DQEJBDEWBBRVGw0FDSiaIi38dWteRUAg/9Pr6DANBgkqhkiG9w0BAQEFAASCAQA3
# PuIKz/OYlGklGNAKT+hKQQbXgRwFjZEgDFpPsV5tkcauXW0lQ1WsZJRQ/8cna8FX
# dW9lDXOx7ow+WsuvRixR51G2VQXMoxhCU3zzWhd790rFT891BkMEtb5pkoADL1TK
# Ckj3q8uY0CJ/HJilHJY+lRBG9w3/uL+ey6IHpaAfjoDUu0pY6dbOl9eoV81T6HP3
# esMku4AlBzUGPi9pum1jx8zhcegSX0xetq44jAo1Hqxo3pz3QtPGfJY/Xshzd8T6
# xVk0RwkIovCQYFrZntw0ZqF/QYIq7jWCoJLOpPBQAtwICxBK12AoBtqGe+Ye0CJT
# j9TPxJhy017cAsmx3heR
# SIG # End signature block
