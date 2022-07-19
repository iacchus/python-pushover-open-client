import click

from . import register_parser
from . import PushoverOpenClient, PushoverOpenClientRealTime

@click.group
def cli():
    pass

@cli.command()
def json():

    @register_parser
    def return_json(raw_data):
        import json
        json_notification = json.dumps(raw_data)

        print(json_notification)

    client = PushoverOpenClientRealTime()
    client.run_forever()


if __name__ == "__main__":

    cli()

