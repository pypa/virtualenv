"""Create a "virtual" Python installation
"""

import sys, os, optparse, shutil
join = os.path.join
py_version = 'python%s.%s' % (sys.version_info[0], sys.version_info[1])

## FIXME: probably other modules for Windows?
REQUIRED_MODULES = ['os', 're', 'posix', 'posixpath', 'stat', 'UserDict', 'readline',
                    'copy_reg', 'types', 'fnmatch',
                    'sre', 'sre_parse', 'sre_constants', 'sre_compile']

def mkdir(path):
    if not os.path.exists(path):
        print 'Creating %s' % path
        os.makedirs(path)
    else:
        if verbose:
            print 'Directory %s already exists' % path

def copyfile(src, dest):
    if not os.path.exists(src):
        # Some bad symlink in the src
        print 'Cannot find file %s' % src
        return
    if os.path.exists(dest):
        print 'File %s already exists' % dest
        return
    if hasattr(os, 'symlink'):
        if verbose:
            print 'Symlinking %s' % dest
        os.symlink(src, dest)
    else:
        if verbose:
            print 'Copying to %s' % dest
        if os.path.isdir(src):
            shutil.copytree(src, dest, True)
        else:
            shutil.copy2(src, dest)

def writefile(dest, content):
    if not os.path.exists(dest):
        if verbose:
            print 'Writing %s' % dest
        f = open(dest, 'wb')
        f.write(content)
        f.close()
        return
    else:
        f = open(dest, 'rb')
        c = f.read()
        f.close()
        if c != content:
            print 'Overwriting %s with new content' % dest
            f = open(dest, 'wb')
            f.write(content)
            f.close()
        elif verbose:
            print 'Content %s already in place' % dest

def rmtree(dir):
    if os.path.exists(dir):
        print 'Deleting tree %s' % dir
        shutil.rmtree(dir)
    else:
        if verbose:
            print 'Do not need to delete %s; already gone' % dir

def make_exe(fn):
    if os.name == 'posix':
        oldmode = os.stat(fn).st_mode & 07777
        newmode = (oldmode | 0555) & 07777
        os.chmod(fn, newmode)
        if verbose:
            print 'Changed mode of %s to %s' % (fn, oct(newmode))

parser = optparse.OptionParser(
    usage="%prog [OPTIONS] DEST_DIR")

parser.add_option(
    '-v', '--verbose',
    action='count',
    dest='verbose',
    default=0,
    help="Increase verbosity")

parser.add_option(
    '--clear',
    dest='clear',
    action='store_true',
    help="Clear out the non-root install and start from scratch")

parser.add_option(
    '--no-site-packages',
    dest='no_site_packages',
    action='store_true',
    help="Don't copy the contents of the global site-packages dir to the "
         "non-root site-packages")

def main():
    options, args = parser.parse_args()
    global verbose
    if not args:
        print 'You must provide a DEST_DIR'
        parser.print_help()
        sys.exit(2)
    if len(args) > 1:
        print 'There must be only one argument: DEST_DIR (you gave %s)' % (
            ' '.join(args))
        parser.print_help()
        sys.exit(2)
    home_dir = args[0]
    lib_dir = join(home_dir, 'lib', py_version)
    inc_dir = join(home_dir, 'include', py_version)
    bin_dir = join(home_dir, 'bin')

    if sys.executable.startswith(bin_dir):
        print 'Please use the *system* python to run this script'
        return

    verbose = options.verbose
        
    if options.clear:
        rmtree(lib_dir)
        rmtree(inc_dir)
        print 'Not deleting', bin_dir

    prefix = sys.prefix
    mkdir(lib_dir)
    stdlib_dir = join(prefix, 'lib', py_version)
    for fn in os.listdir(stdlib_dir):
        if fn != 'site-packages' and os.path.splitext(fn)[0] in REQUIRED_MODULES:
            copyfile(join(stdlib_dir, fn), join(lib_dir, fn))
    writefile(join(lib_dir, 'site.py'), SITE_PY)
    writefile(join(stdlib_dir, 'orig-prefix.txt'), prefix)
    if options.no_site_packages:
        writefile(join(stdlib_dir, 'no-global-site-packages.txt'), '')

    #mkdir(inc_dir)
    #stdinc_dir = join(prefix, 'include', py_version)
    #for fn in os.listdir(stdinc_dir):
    #    copyfile(join(stdinc_dir, fn), join(inc_dir, fn))

    if sys.exec_prefix != sys.prefix:
        exec_dir = join(sys.exec_prefix, 'lib', py_version)
        for fn in os.listdir(exec_dir):
            copyfile(join(exec_dir, fn), join(lib_dir, fn))

    mkdir(bin_dir)
    print 'Copying %s to %s' % (sys.executable, bin_dir)
    py_executable = join(bin_dir, 'python')
    if sys.executable != py_executable:
        shutil.copyfile(sys.executable, py_executable)
        make_exe(py_executable)

    pydistutils = os.path.expanduser('~/.pydistutils.cfg')
    if os.path.exists(pydistutils):
        print 'Please make sure you remove any previous custom paths from'
        print "your", pydistutils, "file."

    print "You're now ready to download ez_setup.py, and run"
    print py_executable, "ez_setup.py"

SITE_PY = """
eJytW3tz27i1/5+fAktPhpIr03ncdjrJeu/k4e36jmPnbrLTTB2PSpGQhZgCuQRpWe30u9/zAEiQ
lBzntppMLJPAwcE5v/MEHIbh67KUOhPrImtyKYxMqnQlyqReGbEsKlGvVJUdlUlVb+FpepvcSCPq
QpitiXFUHASH/+YnOBSfVso4FuBb0tTFOqlVmuT5Vqh1WVS1zETWVErfCKVVrZJc/QNGFDoWh/8+
B8GZFrDzXMlK3MnKAF0jiqX4sK1XhRaTpsQ9P4v/mLyYzoRJK1XWMKCyPINEVkkdaCkzYBNGNgZE
qWp5ZEqZqqVK24GboskzUeZJKsXf/85bo6FRFJhiLTcrWUmhgRmgKYFWiXzAV1WJtMhkLMQbmSa4
AD/vhBUwtRnqzKAYdSHyQt/AnrRMpTFJtRWTRVMTIWJZZAXwpICDWuV5sCmqWzMFlZI+NvBIJAyP
/mYYHrBPXH+MHODxUge/aXU/Y9qAHiRXrxg2lVyqe5EgWfhV3st0bp9N1FJkarkEGeh6ikMCZsCI
XC2OS1LHj1ZDPx0TVy0qE1hDIss8mF/SjDi41KIAZiuUfA24XhsxWSdKA7zeJynx8lels2JjpsQz
yNeIr42pPY6DyQ6WYbTH8kygeJ38G52rW5lvpyCQTysZVNI0eY0QzlQl07qolDREAFjbCnmvDFBI
QP+8acaSs7QZiyM3BVgAqgJNAk0UX4JK9VLdNBXZhFgqwBro8efLX8W70zdnry8sKhwxtrKbNfAM
VEg1Hk+wgDhuTHWcF2CCcXCOP0SSZWgWN7g+8NUNOP6mboIJ7L2Mh3M8FYHY38mFSrRbBvZYg/nT
WgHN+ydMmZkVyOdfD68GG3+9Tyq0cf62WRVgRTpZS7FKDGEZkRH8aOn8FJf16hWgwSCdGkRlWDlZ
ppAeiMSX2aTQUpQAsVxpOQ1AQgsa29ciQOGi0Eek6wESgEIVaHjpPZvSilrCRse0XqGFu8Fb2pkd
ErR6XhcVmTrgX6fkPfJE3xKPhmDP3xbyRmmNDCEWguggooXNrQIkZrE4p1FkyW6QiNjf8Eg0iQaw
hKADTMr7ZF3mEnxlU5Yo5m8YPi0ma+F0nTPiYGRNDpG01m11J/aexy8GqCM261UlgXiz6BndsijA
WMHLEjdlsp7xapuCkBPssCeahJigkTAXv4NEXxvTrGX7ErECnoUAFSyLPC82ILKXQSDEAQ5yYbQP
TngL7+B/oIv/57JOV0HgrdQStqSQ+X2kkAg4caktqi0TPbRZKA+djNLsKYoqkxUt9ThhHzPjjxyM
ew0uitqGId4uarlYqxpd0sIGOcUxSkc1+8dXvG/YBsRaQzJzQzs5rXF7eblKFtIlEQu5REuwSnrV
qh3WDHasSdGzFugfQaLwDsQiFUeQ3Y4Fnc6ylhS2gQYbX6JV2eQ0yCDARAILrUuiv04wCBc2vQF4
cyAN0CFxwE0h/gBv/wAz2qwUyCcFCuBh0EuB+haqrjCkd/4o6IdpN5/XB6SeLW1s4iWXicptXE50
cEYPT6uKzDeVJc6aWWEY2KGuMRm70SBHNPMwDIPAJTBb474W7bf5fNEojHfzeRAEmVzClm8lCmZy
SBnE9CUARiAoxQnMY/+YLAwNcb9/LZR246c0vpJ1U2mcNmtnAVPrNDFyAk+nvBgQms9RM/P5xK4E
LH8EJ4NhhYUdCTcENVMpiN6kE9TUwhQ5/or0ca9IAMPtGrGA9mJTuvguyRtp3Br4qatt9wt+1nG7
znin3ctpO4kVIF47pkgtfZroDpRuJO+2kuviTmbgbVFS3obFr/QGkucyB1uADYEiyQEsq2LdJQQJ
pooMBlATOgsA8pqoOFE4KRxwvi61aSqb+5KfsYk5Y7+sijuF3mWxtS/BOMBu0UScJ7PUCkzDevJG
GwCDgbCnMT3ayAhst2o4QhHfSBLhlXVRISZy5yDhq2v6equLjZ5zsnqC4WUybbWIoLN6xAGdaA/E
zwBaYLKATK4TGlOBGC8QZkfAPGwftguSpWQCCIFlo9sxhUfL5Xa0RU4TcVmkMX0lCMeVRAdx55ag
3MoJw6NEb+P2AaEf/kNKsLnWsgj/bhCsjl7MDYOFPZH00XQec87ZJzCQYgyuZmKp8SAnv6uX18DF
uW+f3rwgOBCfP39m2JgVlUDI2AI3jT5jSf4uLreQMCjIU5wL5oKKYACFkQYyjbHQFEcfRVGy+wV9
cqUGPu4jBPtVXZcvj483m01sC4Ciujk2y+M//vlPf/rzU3YPWUb4ge141mKr4fiY3mEIi390JcNP
TnMDPCrdRyPRmkhywxR7kL+/NCorxMujaetKEMUZRLQGSi8T4//OL9/Ieu4WZSmDbMOOoyfm6En8
woTiiZj4YydYm4JCbFY8bef2fKn7BThFM5u0Kjx6do0E+op1sDDWq87RyEmrSi8LT3K/stYTSuOs
gaN00NmOst3tbifkZJM93lxHrhYw73aoDCoXAd0f8mj7aQePgY8f66Q/bcsH/bNnE1ngsGczoQni
nnhBXcx8o/FAmWUgVy037FnBP/ieDfwrZDwLlrYlR+lNhCQjQeGcknNWrB0BchrU5i6fd1qAEf46
YI9Quchuk0MotC8gKAAGTsQzeiJz401y756yaps8pwJsgNGeVJhwT9FLnAC4nDgCMxFWv4U80qrl
7HKgFNbBDmIF12wIsOUITPgmZjGhlCbhQbgDTj1lPzSbZbyLBCqJxj+OOHF8wgtUBoypnPSBuw/h
rWy5Th0wvD9eEKaclsiizR7bGvqOnTb1YFhZKo2e09NRnOZQRtotqiXjqHvfD/WI072hyBqgFUMn
Dm/QCRLo219kx2G1e9NgXeCXTcjRWhmKTSgmqLczSAqoHKHaEWRJ1FoyjzWy/sb+AybX7td+2QOP
VtAICH/oviRiFDAsHff+QKAYbfEERqBBhGNbpMSPvUEOCPMU1LNteC33GjfRiA2YmRdAyMsA7/Sy
m4YbhCcxthjJQJHyfW1kKf4gQlDf0FIf57r/oyh1RfPEG0CB3jZPTrreykx4TZWTQZOlD+h+75Ra
m2UBCF5AwuL35XyYO9AyPVLUVc9vOy5C6gCEU5/NaycUv+/zw4k3ohOUW8CBqbdIr/vqVuo0bSmD
rh2VnrqHS9nHtEWbR+HcSVSY53J9H81EVCmTFiba5ekYAg8I4lwtQvjRk3Y4ve5RkjknLYi6kxMR
HUffv9Jowt5PmCNL3zGegRCCQXjJ5dXLF9ffQ2QggIen7sGUL0rmaSBI/IwSQvc5IPYhXy4WXyEJ
NbbsvEtUnixycg5HR+gDgHgmF80NZ/Q7afUp7R5iFRZjqQiu6OlsZ4pjrp5eA8RowWg6DpOPaAS4
T5kYM8CVHwaGjCGSnGwfIfA92B2aDuI3S6qN0jtAfEAGuqzAX+JREwvYiEPUxCFUVejxqJaCjEkD
lUxAPZaPE6IDgVZvu1pvm6ri3hQptJTVUQMS56OYY7A/bpLpsSYPxPGFrJGTdlhKtanXuC9Gs2DH
ka02251EnbvZrZtV4ZJcqe9UBXMBPpPol8v3p9FY6XYZnLSbnK9H5yMfb1FI9ztsN7LCib5nDkvo
e6b8/51L1EPo0IoQcm3Ro1uxjQU7qhxd5rFbB9/IIXu9Sgr1HNQhIXhz+pezi/OzNx9ef/rFq6A/
AfAvPx4/F6fvPwtqBOCxFPc4Eiyia2w5Fbp36CyyAv416MCypt5yv86Id+fnNqiv8RATu9poVzE8
535VS21KAuLD0fahbTQhR7m1DO98l/oydP6LhrLmk0pT2M43HRsvsNXeWJuz5/bufJ8qoFiI32Cw
Lwomwb1EeEXnE7VzBxUni/bMewdTceDkyGvmObE6LCy9VMnFZiB2lG11XiSZrSDhSTfZGuxV5PMa
XcemzBWY8KuozfbsNGykdJCxD9taiPma7sjTvemwsh3Iu97LBQwEDnhvdv60A9rvDXDYAewd7FtL
aiRQZx67mCLCQRE3DKCqq6NW9VYHBhSGOWGNSnSgU7D7BLyqgEIE0nENvmqDgEAKA030c5uXXljA
wbgBBMLbdXb0v0gB2YkjK57+3C9f9k2uq/zob6LMGyNsH8rxEu0Q9GjqOzFRsYzF6eXP08FM7xAj
RtawCPMeWVL4A8Se5hCCxfxDRc3uCacHnfzpaZJys7cq8BzI5SKcuCpdu+5mrlIwRbBasMkZyBmr
IUA/kcJ+AGUDRWXcGSk8LLeVulnVWLHB5JjOZ3D4+9efz88uTj8Cn89f8CPq5HExOZ8YmS9dEZMl
dTLjkvUE24noKeGL5wJxdDyf264N/hi+QhoIYPgxfMW18AkvMJrHSQn+GL7iQ2pbMnk7AIw3JW1g
2kvy/Wl97+3ViUSGeW1LMfz4/caOsz4ZymPwTMyWlf7+xuGiHTnwRhQz3MtxGrA3lV2WVoYTN9nv
fw0/do/LMq5kkk12D4K3fodl+FnA1Nt9yemo0+Z/Rlkp3pcBjsaj+2u4XtRoqN2OB7Z9aMF3zk1/
0V6e5Y1LNdovCHHiT576IKtkWVkzGdsBI7B35DIiJn607DpL3AVJEX7RoQ1SPU5aYY+yeTcRG9Di
iZlwrS451GNnFB6SA6GTgolnubPp4fPeHvGQ/NF7tL4LPOgv4P2sw6Wj0aICJMKX3zn34FdT59Zf
isgLdlrqou1K4WezwsTkWX+PO20A11JodlWib+SEac0czT/0hb0nfSNv20PMlRqU5RbdkN7c7wH4
2Cx211yOswEORuNu5XbojfrSwQGjHuGYQpVswLuXTT1hXe0tMXA4mhl1PLDX8fuuNscj2LO0MEz/
vqPyww8Ly+UmbbwaHM5H7QublKQV5Na1oRLLC70uvfCjcRcDT7ooHLZPQz4ea39vEze/gr16+V/X
tI2vyV3i7aS3DrPkr9LbcWgHDNos4f/wdVK6/KHohKw7H7fvMnkn8wKKWEjf8fzya3t+OY3DXVnj
N/jqWEEBf7G5XaJvKX9/+9ezmXh78Sv8/0ZeQoIKwlnPxN+AAfG2qCBR5wsuqIgEzz5rzsCLxsAj
0/bc6JYXXw370NsHNsrtoWz/NLb1FwI72dWa7/ICi7xHuvTVRUt3Vgm/9+9K+Lt3KdMurYT2JYph
/wkxnqoe25Hxql7n6Di9urRT51V4fvb29OLjaVzfI67cr6FXt/b7dLgj22ipsKicifZJ2uCT62mX
Qf4i83JHAmkTeHfajAm8iFYwtk3a+eJpIjYV1hsVJPBYhYlymxVpjCMBVXTfR9QbyCinXq7+zYjX
CzdIa8K1o5/W4mOQhvgy9AAhDKQ5dk80kxhKFnjTgh/H4e6YNBOHSXVj4Mfh7SYzfrLHR+a0wSGn
3a4n/emtE1qxnC09H0zE2kmrCXenKFeJWS9S/4LNpXZXh8G9YJsHBiZNXgup0yKjmonucIKX9e/E
sJ0wWti300URqnrzTbI1XmsSCvoQVw3pGloCFS91vaFieZ/csi/GyzpQ5tNwoE6MUi1ReFNNk67Y
jrk82OH+yPVtlH7xPBoJmRed0fXxtEvqYJ+YQjFHN7K2++cHk+nVsy6sYvdfp/6BaJSWEHF8pByA
+ywPDw9D8d/fzgSYlTgviltIUYB2P9LZEH5Or/fEcLu5VlvjLNe9iQGS6UpewQMsvL3njabOzwNT
SSGy/eloRKibqMWjGz+IidwDoSaKG4EtnTZ2/KYVXenHSl2iy7V/GUG3zpGOgyT4higxqVIRt0dB
H9uiwcss2LWxeJH3gHi1puvs8BZvHXLZucJsi24Qtuhp2TkRIREOQX/v7Gp0MY7ugwCf8w9by+b8
TKu6O8l96t+9OtWEYMxjOaRYXIlkg5bh9jEQhncvqgfVLtssHoRoL3sv0iu/fzPYJb/+Fu8AbbC0
Yrl0nMJDp6S0kFXqgipqTKWq9si4cUiHJ0O9bwNQHOxgKQQPT4Ehay26fftDqxef00vqSB65lWwb
vm7/6KNKFDZ/9ODYIY679dFnmFaQLW7dlymsckFdQpsP9NYSP9geFR7l9W66+heKGm1vsFLPVnTX
WoEO/dVE6yBbOPZ8hPfHNS19Bq1N7LsLr97JI5arxNudquomyef2DxHmmLLN27NYy2d7EeXBK1Zt
zgIJdgGp5xG3IDF3cN1qlCfkx7k7GIV63ZbrsX+5o38Poj1zt2dMz2ZDOtP+Xh44UbYbsqHze46e
x8uhqJyEviFGGtO7qhuwGmAlmDOHBbCeGdxudThHSXNjBXBeFkbdh+2fF/CtVu/Yx2llAQ54fPON
SLznzrp/6N+7J7iLt6Go/Nc7J+xTxnjirthsj6X9In1woBDYp9z9db959ZZ75LIf1kGX2rj3XTSy
ZjMy1oD9ib1ivMcnTNvGPp7LGYwnmAy14URaKq3TSuge/fDP/Og0opZQgthTftBiKr1ronRDlEnV
/b8nrMCVJJgW81/uzdqb/jSOQ6dp/4QFU+NUxk4Dq8Tg3XBECx6GjvbngyWT+R4pBAEbhb1Fiftw
FsKdiLDF7AlUF21ltffio52FX59UM+rwYDtx6pO8xhv6mEoj3PHuOeBnzhY4twiynAT/B8e/kcQ=
""".decode('base64').decode('zlib')

      
if __name__ == '__main__':
    main()

