"""Utility to dump bootstrap options in a 'bootstrap.ini' file
"""

import json
import os
from argparse import ArgumentParser
from ConfigParser import ConfigParser

parser = ArgumentParser()
parser.add_argument('destdir')
parser.add_argument('options',
                    help="JSON serialization of options.")
parser.add_argument('--filename', default='bootstrap.ini')

arguments = parser.parse_args()
dest_path = os.path.join(arguments.destdir, arguments.filename)
print("Dumping bootstrap options to %r" % dest_path)

conf = ConfigParser()
conf.add_section('bootstrap')
options = json.loads(arguments.options)

# changing namings for clearer ones out of context and the ones
# anybox-oe-tarball-deploy settled on
version = options.pop('version', None)
btype = options.pop('type', None)
if version is not None:
    options['buildout-version'] = version
if btype is not None:
    options['bootstrap-type'] = btype

for k, v in options.items():
    conf.set('bootstrap', k, v)

with open(dest_path, 'w') as f:
    f.write("# BOOTSTRAP OPTIONS\n"
            "# These can be used by an automatic agent or serve\n"
            "# as a mere reminder to human operators of what the\n"
            "# buildbot did, to allow for reproducibility.\n"
            "\n"
            "# Per option details:\n"
            "# - 'bootstrap-type': the major buildout version (v1, v2..)\n"
            "#                     this bootstrap was taken from\n"
            "#           (has impact on available command-line options)\n"
            "# - 'buildout-version': the precise zc.buildout intermediate\n"
            "#                       version to use *for the bootstrap*\n"
            "#                       (independent from the one in buildout\n"
            "#                        config file, but future versions\n"
            "#                        might not be able to bootstrap this\n"
            "#                        buildout properly, with obscure errors)"
            "\n"
            "# - 'script' is the name of the bootstrap python script\n"
            "#    to use (if not 'bootstrap.py')\n"
            "\n")
    conf.write(f)
