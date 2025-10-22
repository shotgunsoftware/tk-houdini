set -e

REPOS="tk-core
tk-framework-qtwidgets
tk-framework-shotgunutils
tk-framework-widget
tk-houdini-alembicnode
tk-multi-loader2
tk-multi-setframerange
tk-multi-workfiles2
tk-multi-snapshot
"

for repo in $REPOS; do
    echo
    echo
    echo "# ${repo}"
    echo

    if ! [ -e "../${repo}" ]; then
        echo "${repo} does not exist, cloning"
        baseUrl="$(dirname "$(git config --get remote.origin.url)")"
        git clone "${baseUrl}/${repo}.git" "../${repo}"

    else
        echo "${repo} already exists, pulling latest changes"
        git -C "../${repo}" fetch
        git -C "../${repo}" checkout .
        git -C "../${repo}" clean -f -d -x .
        git -C "../${repo}" switch master
        git -C "../${repo}" merge
    fi

    git -C "../${repo}" clean -f -d -x .
done
