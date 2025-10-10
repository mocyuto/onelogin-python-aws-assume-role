# onelogin-python-aws-assume-role

[![Lint and Format](https://github.com/mocyuto/onelogin-python-aws-assume-role/actions/workflows/lint.yml/badge.svg)](https://github.com/mocyuto/onelogin-python-aws-assume-role/actions/workflows/lint.yml)

Assume an AWS Role and get temporary credentials using Onelogin.

Users will be able to choose from among multiple AWS roles in multiple AWS accounts when they sign in using OneLogin in order to assume an AWS Role and obtain temporary AWS access credentials.

This is really useful for customers that run complex environments with multiple AWS accounts, roles and many different people that need periodic access as it saves manually generating and managing AWS credentials.

This repository contains a python script at [src/aws_assume_role/aws_assume_role.py](https://github.com/onelogin/onelogin-python-aws-assume-role/blob/master/src/aws_assume_role/aws_assume_role.py) that you can execute using `onelogin-aws-assume-role` in order to retrieve the AWS credentials.

OneLogin's Smart MFA cannot be enforced with OneLogin's AWS CLI utility

## AWS and OneLogin prerequisites

The "[Configuring SAML for Amazon Web Services (AWS) with Multiple Accounts and Roles](https://onelogin.service-now.com/support?id=kb_article&sys_id=66a91d03db109700d5505eea4b9619a5)" guide explains how to:

- Add the AWS Multi Account app to OneLogin
- Configure OneLogin as an Identity Provider for each AWS account
- Add or update AWS Roles to use OneLogin as the SAML provider
- Add external roles to give OneLogin access to your AWS accounts
- Complete your AWS Multi Account configuration in OneLogin

## Getting started

This project uses [uv](https://github.com/astral-sh/uv), a fast Python package manager.

### Install uv

```bash
# macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

```

### Quick installation (Recommended for end users)

You can install this package as a standalone tool using `uv tool install` or run it directly with `uvx`:

```bash
# Install as a tool (recommended for regular use)
uv tool install git+https://github.com/mocyuto/onelogin-python-aws-assume-role.git@v2.x.x

# Run directly without installation (recommended for one-time use)
uvx --from git+https://github.com/mocyuto/onelogin-python-aws-assume-role.git onelogin-aws-assume-role
```

After installing with `uv tool install`, you can run the command from anywhere:

```bash
onelogin-aws-assume-role --profile profilename
```

## Settings

The python script uses a settings file, where [OneLogin SDK properties](https://github.com/onelogin/onelogin-python-sdk#getting-started) are placed.

Is a json file named `onelogin.sdk.json` as follows:

```json
{
  "client_id": "",
  "client_secret": "",
  "region": "",
  "ip": ""
}
```

Where:

- `client_id` - Onelogin OAuth2 client ID
- `client_secret` - Onelogin OAuth2 client secret
- `region` - Indicates where the instance is hosted. Possible values: 'us' or 'eu'.
- `ip` - Indicates the IP to be used on the method to retrieve the SAMLResponse in order to bypass MFA if that IP was previously whitelisted.

For security reasons, IP only can be provided in `onelogin.sdk.json`.
On a shared machine where multiple users has access, That file should only be readable by the root of the machine that also controls the
client_id / client_secret, and not by an end user, to prevent him manipulate the IP value.

Place the file in the `~/.onelogin` directory or in the same path where the python script is invoked or provide the path with the -c option.

There is an optional file `onelogin.aws.json`, that can be used if you plan to execute the script with some fixed values and avoid providing it on the command line each time.

```json
{
  "app_id": "123456",
  "subdomain": "myolsubdomain",
  "username": "user@example.com",
  "profile": "profile-1",
  "duration": 3600,
  "aws_region": "us-west-2",
  "aws_account_id": "",
  "aws_role_name": "",
  "mfa_device_type": "",
  "save_password": false,
  "profiles": {
    "profile-1": {
      "aws_account_id": "",
      "aws_role_name": "",
      "aws_region": "",
      "app_id": ""
    },
    "profile-2": {
      "aws_account_id": ""
    }
  }
}
```

Where:

- `app_id` - Onelogin AWS integration app id
- `subdomain` - Needs to be set to the correct subdomain for your AWS integration
- `username` - The email address that is used to authenticate against Onelogin
- `profile` - The AWS profile to use in ~/.aws/credentials
- `duration` - Desired AWS Credential Duration in seconds. Default: 3600, Min: 900, Max: 43200
- `aws_region` - AWS region to use
- `aws_account_id` - AWS account id to be used
- `aws_role_name` - AWS role name to select
- `mfa_device_type` - MFA Device Type to use (to skip MFA device selection prompt, e.g., 'Google Authenticator', 'OneLogin Protect')
- `save_password` - If set to `true`, saves OneLogin password to OS keychain after successful authentication (default: `false`)
- `profiles` - Contains a list of profile->account id, and optionally role name mappings. If this attribute is populated `aws_account_id`, `aws_role_name`, `aws_region`, and `app_id` will be set based on the `profile` provided when running the script.

**Note**: The values provided on the command line will take precedence over the values defined on this file and, values defined at the _global_ scope in the file, will take precedence over values defined at the `profiles` level. IN addition, each attribute is treating individually, so be aware that this may lead to somewhat strange behaviour when overriding a subset of parameters, when others are defined at a _lower level_ and not overridden. For example, if you had a `onelogin.aws.json` config file as follows:

```json
{
  ...
  "aws_region": "eu-east-1",
  "profiles": {
    "my-account": {
      "aws_account_id": "11111111",
      "aws_role_name": "Administrator"
    }
  }
}
````

And, you you subsequently ran the application with the command line arguments `--profile my-account --aws-account-id 22222222` then the application would ultimately attempt to log in with the role `Administrator` on account `22222222`, with region set to `eu-east-1` and, if successful, save the credentials to profile `my-account`.

In addition, there is another optional file that can be created to give more human readable names to the account list, named `accounts.yaml`, which should be placed in the same path where the python script is invoked:

```yaml
accounts:
  "987654321012": Prod account
  "123456789012": Dev Account
```

This isn't needed for the script to function but it provides a better user experience.

### How the process works

#### Step 1. Provide OneLogin data.

- Provide OneLogin's username/mail and password to authenticate the user
- Provide the OneLogin's App ID to identify the AWS app
- Provide the domain of your OneLogin's instance.

_Note: If you're bored typing your
username (`--onelogin-username`),
App ID (`--onelogin-app-id`),
subdomain (`--onelogin-subdomain`) or
AWS region (`--aws-region`)
every time, you can specify these parameters as command-line arguments and
the tool won't ask for them any more._

You can specify
OTP Code (`--otp`)
and the cli will use this otp only for the first interaction
requiring a manual OTP Code

You can also specify
MFA Device Type (`--mfa-device-type`)
to skip the MFA device selection prompt. This is useful when you have multiple MFA devices registered
and want to use a specific type without being prompted every time. Common device types include:

- `Google Authenticator`
- `OneLogin Protect`
- `Yubico YubiKey`
- `OneLogin SMS`

You can find your MFA Device Type by running the tool once and noting the device type from the MFA device
selection screen, or by configuring it in the `onelogin.aws.json` file with the `mfa_device_type` field.

_Note: Specifying your password directly with `--onelogin-password` is bad practice,
you should use that flag together with password managers, eg. with the OSX Keychain:
`--onelogin-password $(security find-generic-password -a $USER -s onelogin -w)`,
so your password won't be saved in you command line history.
Please note that your password **will** be visible in your process list,
if you use this flag (as the expanded command line arguments are part of the name of the process)._

With that data, a SAMLResponse is retrieved. And possible AWS Role are retrieved.

#### Step 2. Select AWS Role to be assumed.

- Provide the desired AWS Role to be assumed.
- Provide the AWS Region instance (required in order to execute the AWS API call).

#### Step 3. AWS Credentials retrieved.

A temporal AWS AccessKey and secretKey are retrieved in addition to a sessionToken.
Those data can be used to generate an AWS BasicSessionCredentials to be used in any AWS API SDK.



For more info execute:

```sh
> onelogin-aws-assume-role --help
```

## Development

After checking out the repo, install all dependencies including development dependencies:

```sh
uv sync
```

Development dependencies are automatically included with `uv sync`.

### Docker installation method

- `git clone git@github.com:onelogin/onelogin-python-aws-assume-role.git`
- `cd onelogin-python-aws-assume-role`
- Enter your credentials in the `onelogin.sdk.json` file as explained above
- Save the `onelogin.sdk.json` file in the root directory of the repo
- `docker build . -t awsaccess:latest`
- `docker run -it -v ~/.aws:/root/.aws -v $(pwd)/onelogin.sdk.json:/root/.onelogin/onelogin.sdk.json awsaccess:latest onelogin-aws-assume-role --onelogin-username {user_email} --onelogin-subdomain {subdomain} --onelogin-app-id {app_id} --aws-region {aws region} --profile default`

Note: The Docker image is now based on uv for faster and more efficient dependency management.

### Pre-commit hooks (Optional)

To automatically format and lint code before committing:

```sh
# Install pre-commit hooks
uv run pre-commit install

# Run hooks manually on all files
uv run pre-commit run --all-files
```

### Running tests

```sh
uv run pytest
```

### Linting and formatting

```sh
# Check code quality
uv run ruff check src/

# Automatically fix issues
uv run ruff check --fix src/

# Format code
uv run ruff format src/

# Check formatting without changing files
uv run ruff format --check src/
```



## Contributing

Bug reports and pull requests are welcome on GitHub at https://github.com/onelogin/onelogin-python-aws-assume-role. This project is intended to be a safe, welcoming space for collaboration, and contributors are expected to adhere to the [Contributor Covenant](http://contributor-covenant.org) code of conduct.

## License

The gem is available as open source under the terms of the [MIT License](http://opensource.org/licenses/MIT).

## Code of Conduct

Everyone interacting in the OneLogin Assume AWS Role project’s codebases, issue trackers, chat rooms and mailing lists is expected to follow the [code of conduct](https://github.com/onelogin/onelogin-python-aws-assume-role/blob/master/CODE_OF_CONDUCT.md).
