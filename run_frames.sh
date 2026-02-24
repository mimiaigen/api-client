python mimiaigen_v2v_client.py \
--input-media './examples/frames_dir/' \
--prompt "$(cat <<'EOF'
Make it look like a snowy winter day.
EOF
)" \
--output-size 1280 \
--input-fps 15.0 \
--output-fps 15.0 \
--output-format both \
--api-key <your_api_key>
