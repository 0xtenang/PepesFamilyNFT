# Builds the launch page: tools/launch/template.html with the contracts' creation code from out/ (forge build).
#   python3 tools/launch/build.py [ethers script src] > page.html
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def code(name, src='src'):
    return json.load(open(os.path.join(ROOT, 'out', f'{name}.sol', f'{name}.json')))['bytecode']['object']
codes = {'specs': code('FrogCraftSpecs'), 'data': code('FrogCraftArtData'), 'art': code('FrogCraftArt'),
         'pepes': code('PepesFamily'), 'validator': code('DevTransferValidator')}
src = sys.argv[1] if len(sys.argv) > 1 else 'https://cdn.jsdelivr.net/npm/ethers@6.13.4/dist/ethers.umd.min.js'
t = open(os.path.join(ROOT, 'tools', 'launch', 'template.html')).read()
sys.stdout.write(t.replace('__ETHERS_SRC__', src).replace('__BYTECODES__', json.dumps(codes)))
