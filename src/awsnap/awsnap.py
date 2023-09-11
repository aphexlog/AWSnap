from pathlib import Path
import boto3
import webbrowser
import argparse
import subprocess
import os
import botocore.exceptions
import configparser
import cmd
import logging

# Logging configuration
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


class AWSnapShell(cmd.Cmd):
    prompt = "(awsnap) "

    def do_open(self, profile):
        """Open AWS Console with a specific profile"""
        try:
            sso_url = get_sso_url_from_profile(profile)
            open_aws_console(profile, sso_url)
            logging.info(
                f"Successfully opened AWS console for profile {profile}"
            )
        except Exception as e:
            logging.error(
                f"Failed to open AWS console for profile {profile}: {str(e)}"
            )

    def do_login(self, profile):
        """Authenticate with AWS SSO"""
        authenticate_sso(profile)

    def do_list(self, args):
        """List available AWS profiles"""
        list_profiles()

    def do_exit(self, args):
        """Exit the interactive shell"""
        return True

    def default(self, args):
        print(f"Unknown command: {args} (type 'help' for available commands)")


def list_profiles():
    config_path = Path.home() / ".aws" / "config"
    config = configparser.ConfigParser()
    config.read(config_path)

    profiles = [
        section.replace("profile ", "")
        for section in config.sections()
        if section.startswith("profile ")
    ]

    print("Available Profiles:")
    for profile in profiles:
        print(f"  - {profile}")


def open_aws_console(profile, sso_url):
    sso_url, region = get_sso_url_from_profile(profile)
    try:
        # Create the session with the region if available
        session = (
            boto3.Session(profile_name=profile, region_name=region)
            if region
            else boto3.Session(profile_name=profile)
        )

        if not sso_credentials_exist(session):
            authenticate_sso(profile)
            if not sso_credentials_exist(session):
                raise Exception("SSO authentication failed")

        webbrowser.open(sso_url)
        logging.info(f"Opened AWS console for profile {profile}")

    except Exception as e:
        logging.error(
            f"Failed to open AWS console for profile {profile}: {str(e)}"
        )
        raise


def sso_credentials_exist(session):
    try:
        session.client("sts").get_caller_identity()
        return True
    except (
        botocore.exceptions.BotoCoreError,
        botocore.exceptions.ClientError,
    ):
        return False


def authenticate_sso(profile):
    try:
        sso_start_url = get_sso_url_from_profile(profile)

        if not sso_start_url:
            raise ValueError(
                f"Failed to obtain SSO Start URL for profile {profile}"
            )

        # Execute the AWS CLI command for SSO login
        command = ["aws", "sso", "login", "--profile", profile]
        subprocess.run(command, check=True)

        logging.info(f"Successfully authenticated SSO for profile {profile}")
        return True

    except subprocess.CalledProcessError as e:
        logging.error(
            f"An error occurred during SSO authentication for profile {profile}: {str(e)}"
        )
        raise  # Raising exception to handle it at a higher level if needed
    except Exception as e:
        logging.error(
            f"An error occurred during SSO authentication for profile {profile}: {str(e)}"
        )
        raise  # Raising exception to handle it at a higher level if needed


def get_sso_url_from_profile(profile):
    config = configparser.ConfigParser()
    config.read(f"{os.path.expanduser('~')}/.aws/config")

    sso_session = config.get(f"profile {profile}", "sso_session")
    sso_start_url = config.get(f"sso-session {sso_session}", "sso_start_url")
    region = config.get(
        f"profile {profile}", "region", fallback=None
    )  # Fetching the region

    return sso_start_url, region


def export_temporary_aws_credentials(profile):
    session = boto3.Session(profile_name=profile)
    credentials = session.get_credentials()
    access_key = credentials.access_key
    secret_key = credentials.secret_key
    session_token = credentials.token

    credentials_path = Path.home() / ".aws" / "credentials"
    config = configparser.ConfigParser()

    # Read existing credentials if they exist
    if credentials_path.exists():
        config.read(credentials_path)

    if "default" not in config.sections():
        config.add_section("default")

    config.set("default", "aws_access_key_id", access_key)
    config.set("default", "aws_secret_access_key", secret_key)
    config.set("default", "aws_session_token", session_token)

    with open(credentials_path, "w") as f:
        config.write(f)

    logging.info(
        "Temporary AWS credentials have been written to the default profile in ~/.aws/credentials"
    )


def run_shell_command(profile, command):
    export_temporary_aws_credentials(profile)
    print(f"Running command for profile {profile}: {command}")
    os.system(command)


def main():
    parser = argparse.ArgumentParser(
        description="AWSnap: AWS SSO Utility",
    )
    parser.add_argument("-p", "--profile", help="AWS profile name")
    parser.add_argument(
        "--console", action="store_true", help="Open AWS console"
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Enter interactive mode",
    )
    parser.add_argument(
        "command",
        nargs="*",
        help="Command followed by its arguments to run in the shell",
    )

    args = parser.parse_args()

    if args.interactive:
        AWSnapShell().cmdloop()
    elif args.command:
        shell_command = " ".join(args.command)
        run_shell_command(args.profile, shell_command)
    elif args.console:  # Open console when --console flag is used
        sso_url, _ = get_sso_url_from_profile(args.profile)
        open_aws_console(args.profile, sso_url)
    elif args.profile:  # Export credentials when --profile flag is used
        export_temporary_aws_credentials(args.profile)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
