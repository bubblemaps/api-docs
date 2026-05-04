# Mintlify Starter Kit

Click on `Use this template` to copy the Mintlify starter kit. The starter kit contains examples including

- Guide pages
- Navigation
- Customizations
- API Reference pages
- Use of popular components

### Development

Install the [Mintlify CLI](https://www.npmjs.com/package/mintlify) to preview the documentation changes locally. To install, use the following command

```
npm i -g mintlify
```

Run the following command at the root of your documentation (where docs.json is)

```
mintlify dev
```

### Publishing Changes

Install our Github App to auto propagate changes from your repo to your deployment. Changes will be deployed to production automatically after pushing to the default branch. Find the link to install on your dashboard. 

#### Troubleshooting

- Mintlify dev isn't running - Run `mintlify install` it'll re-install dependencies.
- Page loads as a 404 - Make sure you are running in a folder with `docs.json`

# Open API schema preparation

Create a new openapi file that filters out unwanted endpoints and schemas:

```
python prepare-openapi-schema.py openapi.json \
  --password "SWAGGER_PASSWORD" \
  --version "0.2.0" \
  --pattern "/chains" \
  --pattern "/maps/*" \
  --pattern "/v0/*"
```

Possible to pass a local file instead:

```
python prepare-openapi-schema.py openapi.json \
  --input-file input.json \
  --version "0.2.0" \
  --pattern "/chains" \
  --pattern "/maps/*" \
  --pattern "/v0/*"
```