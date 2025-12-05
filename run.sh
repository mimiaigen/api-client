python client.py \
--image '/Users/shamangary/codeDemo/data/bonsai/image/bonsai_farm_example.png' \
--prompt "$(cat <<'EOF'
Make a 2x2 grid, each cell isolate an item of the given image.

For example, you can see multiple tree with farm ground which bulge up near the tree root.

For the cell 1 and 2 in the 1st row, generate single tree (until root, no ground) similar as given image but slightly different in different way to show diversity.

For the cell 3 and 4 in the 2nd row, generate the single bulge row (no wire, no tree, straight row) similar as given image but slightly different in different way to show diversity. View angle 45 degree, top-right to bottom-left diagonal to show the whole subject in 3D

Each cell has full view of such subject. Realistic, not toy, not cartoon.

Each cell has transparent background except for the subject.
EOF
)" \
--api-key <your_api_key> \
--batch-size 1