import subprocess

subprocess.run(['docker', 'compose', 'exec', '-T', 'app', 'mkdir', '-p', '/tmp/characterization'], check=True)
for name in ('test_api.py', 'suggestion.json', 'topics.json'):
    subprocess.run(['docker', 'compose', 'cp', f'tests/characterization/{name}', f'app:/tmp/characterization/{name}'], check=True)
subprocess.run(['docker', 'compose', 'exec', '-T', '-e', 'HELPDESK_URL=http://edge', 'app', 'python', '-m', 'unittest', 'discover', '-s', '/tmp/characterization', '-v'], check=True)
