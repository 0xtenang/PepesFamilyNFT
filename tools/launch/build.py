# Builds the launch page: tools/launch/template.html with the contracts' creation code from out/ (forge build).
#   python3 tools/launch/build.py [ethers script src] > page.html
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def code(name, src='src'):
    return json.load(open(os.path.join(ROOT, 'out', f'{name}.sol', f'{name}.json')))['bytecode']['object']
frames = sorted(int(f[11:-4]) for f in os.listdir(os.path.join(ROOT, 'src')) if f.startswith('ImdPepeData') and f.endswith('.sol'))
codes = {'specs': code('ImdPepeSpecs'), 'parts': code('ImdPepeParts'), 'art': code('ImdPepeArt'),
         'pepes': code('PepesFamily'), 'validator': code('DevTransferValidator')}
codes.update({f'data{i}': code(f'ImdPepeData{i}') for i in frames})
src = sys.argv[1] if len(sys.argv) > 1 else 'https://cdn.jsdelivr.net/npm/ethers@6.13.4/dist/ethers.umd.min.js'
t = open(os.path.join(ROOT, 'tools', 'launch', 'template.html')).read()
sys.stdout.write(t.replace('__ETHERS_SRC__', src).replace('__BYTECODES__', json.dumps(codes)))
