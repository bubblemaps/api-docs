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

Rename previous `openapi.json` to `openapi-old.json` before anything.

Create a new openapi file that filters out unwanted endpoints and schemas. Deprecated **properties** are removed from the published spec (deprecated **endpoints** are kept as-is when included via patterns).

```
python prepare-openapi-schema.py openapi.json \
  --password "SWAGGER_PASSWORD" \
  --version "0.3.0" \
  --pattern "/v0/*"
```

Possible to pass a local file instead:

```
python prepare-openapi-schema.py openapi.json \
  --input-file ~/Downloads/input.json \
  --version "0.3.0" \
  --pattern "/v0/*"
```

Be careful not to put the input file at the root of the project, it can be detected and used by mintlify instead of `openapi.json`

The script also writes a structured JSON report of removed fields to `openapi-deprecated.json`. Use this to add MDX callouts on endpoint pages. Don't hesitate to use AI to quickstart documentation changes:

> Read AGENTS.md, then update the documentation based on the difference between openapi-old.json and openapi.json, and on the deprecated response attributes that are listed in openapi-deprecated.json. Update endpoints, parameters, changelog, etc, following the existing style of the documentation.