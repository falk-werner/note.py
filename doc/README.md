# note.py development documentation

## Install development requirements

````bash
pip3 install -r doc/requirements.txt
pip3 install pytest pylint coverage 
````

## Update documentation

    ./doc/create_doc.sh

The resulting resulting HTML documentation is located at the `doc/html` subdirectory.

## Running pylint

    pylint note.py

## Runnting Unit-Tests

    pytest

## Generate code coverage report

````bash
coverage run
coverage html
````

The resulting test coverage report is located at the `coverage/html` subdirectory.
