import mido
import simplecli


@simplecli.wrap
def main(
    list_devices: bool = False,  # List available MIDI devices
    input_device: None | str = None,  # MIDI device to use for input
    output_device: None | str = None,  # MIDI device to use for output
    filename: None | str = None,  # File to write sysex dump to
    channel: int = 1,  # MIDI channel to transmit on
) -> None:
    if list_devices:
        print("Input Devices:")
        for i in mido.get_input_names():
            print(f"\t'{i}'")
        print("Output Devices:")
        for o in mido.get_output_names():
            print(f"\t'{o}'")
        exit()
    if not input_device or not output_device:
        exit("ERROR: An input and output device is required!")
    if input_device not in mido.get_input_names():
        exit(f"ERROR: {input_device} is not a valid input device")
    if output_device not in mido.get_output_names():
        exit(f"ERROR: {output_device} is not a valid output device")
    if not filename:
        exit("ERROR: output filename required")

    patch_request = mido.Message(
        "sysex",
        data=[0, 0, 0x1b, 0x0b, channel - 1, 0x14],
    )
    inp = mido.open_input(input_device)
    outp = mido.open_output(output_device)
    outp.send(patch_request)
    patch = inp.receive()
    mido.write_syx_file(filename, [patch])
    print(patch)
