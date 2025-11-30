# api-client
This is physical-data-agent api client to call end2end generation including 3D asset and 4D interaction.


### Step.1 Create acccount

[mimiaigen.com](https://mimiaigen.com/api)


### Step.2 Create api key

Go to [api page](https://mimiaigen.com/api)

Choose your api-key name, press create and copy the api key.


### Step.3 Calling the client with image input

```
python client.py --target "apple tree" \
--image './examples/apple_tree.jpeg' \
--api-key <your_api_key> \
--batch-size 1

python client.py --target "pistachio tree" \
--image './examples/pistachio_tree.png' \
--api-key <your_api_key> \
--batch-size 1

python client.py --target "vine tree" \
--image './examples/vine_tree.png' \
--api-key <your_api_key> \
--batch-size 1

python client.py --target "strawberry bed with black plastic cover" \
--image './examples/strawberry_bed.png' \
--prompt "Isolate the input image into a single row of {TARGET} top-down 45 degree view, transparent background, and generate in different styles with realistic variations, no ground, no tool, not toy, only realistic {TARGET}" \
--api-key <your_api_key> \
--batch-size 1
```

Or instead calling with target or prompt only

```
python client.py --target "a single apple" \
--api-key <your_api_key> \
--batch-size 1

python client.py --target "a single apple" \
--prompt 'Generate {TARGET} in a diverse way.' \
--api-key <your_api_key> \
--batch-size 1

```
