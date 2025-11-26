# api-client
This is physical-data-agent api client to call end2end generation including 3D asset and 4D interaction.


### Step.1 Create acccount

[mimiaigen.com](https://mimiaigen.com/api)


### Step.2 Create api key

Go to [api page](https://mimiaigen.com/api)

Choose your api-key name, press create and copy the api key.


### Step.3 Calling the client

```
python client.py --target "apple tree" \
--image './examples/apple_tree.jpeg' \
--api-key <your_api_key> \
--batch-size 1

python client.py --target "pistachio tree" \
--image './examples/pistachio_tree.jpeg' \
--api-key <your_api_key> \
--batch-size 1

python client.py --target "vine tree" \
--image './examples/vine_tree.jpeg' \
--api-key <your_api_key> \
--batch-size 1

python client.py --target "strawberry bed with black plastic cover" \
--image './examples/strawberry_bed.jpeg' \
--api-key <your_api_key> \
--batch-size 1
```

