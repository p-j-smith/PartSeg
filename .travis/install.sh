#!/usr/bin/env bash
mkdir -p ~/cache/
wget -N https://4dnucleome.cent.uw.edu.pl/PartSeg/Downloads/test_data.tbz2 -P ~/cache/

tar -jxf ~/cache/test_data.tbz2 -c .

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then

    # Install some custom requirements on macOS
    # e.g. brew install pyenv-virtualenv
    brew upgrade pyenv

    case "${TOXENV}" in
        py36)
            pyenv install 3.6.8
            pyenv global 3.6.8
            # Install some custom Python 3.6 requirements on macOS
            ;;
        py37)
            pyenv install 3.7.2
            pyenv global 3.7.2
            # Install some custom Python 3.7 requirements on macOS
            ;;
    esac
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/shims:$PATH"

    pip install pytest
else
    echo "linux"
    # Install some custom requirements on Linux
fi

pip install pip==18.1
pip install pyinstaller cython numpy
pip install ./package