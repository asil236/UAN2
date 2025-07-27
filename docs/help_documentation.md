# Unreal Audio Normalizer

Professional audio normalization tool with LUFS targeting for Unreal Engine projects.

## Features

- **LUFS Normalization**: Precise audio loudness normalization to industry standards
- **Batch Processing**: Process multiple audio files simultaneously
- **Multiple Formats**: Support for WAV, MP3, FLAC, OGG, M4A, AAC input formats
- **Custom Presets**: Configurable LUFS presets with custom suffixes and colors
- **Audio Preview**: Built-in audio player for each file
- **Mono Conversion**: Convert stereo files to mono during processing
- **Drag & Drop**: Easy file management with drag and drop support
- **Override Output**: Option to specify custom output directory

## Supported Audio Formats

- **Input**: WAV, MP3, FLAC, OGG, M4A, AAC
- **Output**: 24-bit WAV files

## System Requirements

- Windows 10/11 (64-bit)
- Minimum 4GB RAM
- 100MB free disk space

## Installation

### Option 1: Download Pre-built Executable
1. Go to the [Releases](https://github.com/yourusername/unreal-audio-normalizer/releases) page
2. Download the latest `UnrealAudioNormalizer.exe`
3. Run the executable - no installation required!

### Option 2: Build from Source

#### Prerequisites
- Python 3.9 or higher
- Git

#### Steps
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/unreal-audio-normalizer.git
   cd unreal-audio-normalizer
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python main.py
   ```

#### Building Executable
On Windows, you can use the provided build script:
```bash
build.bat
```

Or manually with PyInstaller:
```bash
pip install pyinstaller
pyinstaller audio_normalizer.spec
```

## Usage

### Basic Workflow
1. **Add Files**: Click "Add Audio Files" or drag & drop audio files into the application
2. **Set Target LUFS**: Use the slider to select your desired LUFS level (default presets available)
3. **Configure Output**: Set file suffix and optionally choose override output folder
4. **Process**: Click "Normalize Checked" or "Normalize All"

### LUFS Presets
The application comes with predefined LUFS targets:
- **-12 LUFS**: SFX (Sound Effects)
- **-14 LUFS**: Music
- **-16 LUFS**: Dialog
- **-18 LUFS**: UI (User Interface)
- **-20 LUFS**: Ambient

You can customize these presets or add new ones using the "Configure LUFS Presets" button.

### File Management
- **Checkboxes**: Select which files to process
- **Filters**: View specific file types (mono/stereo, WAV/MP3, out of tolerance)
- **Search**: Filter files by name
- **Audio Preview**: Click play button to preview any file

### Advanced Features
- **Tolerance Setting**: Set LUFS tolerance for color-coding (green = within tolerance, red = outside)
- **Mono Conversion**: Convert stereo files to mono during normalization
- **Override Output**: Specify custom output directory instead of using input file locations

## Configuration

The application stores its configuration in:
- **Windows**: `%APPDATA%\UnrealAudioNormalizer\lufs_config.json`

This file contains your custom LUFS presets and can be backed up or shared between installations.

## Troubleshooting

### Common Issues

#### "Cannot find specified file" Error
- Ensure all input files exist and are accessible
- Check that you have write permissions to the output directory
- Try running as administrator if output directory is protected

#### MP3 Files Not Loading
- The application includes FFmpeg for MP3 support
- If issues persist, try converting MP3 to WAV first using another tool

#### Audio Preview Not Working
- Check Windows audio settings
- Ensure no other application is using exclusive audio access
- Restart the application

#### Memory Issues with Large Files
- Process files in smaller batches
- Close other applications to free up RAM
- Consider converting very large files to lower sample rates first

### Performance Tips
- Process similar file types together for better performance
- Use SSD storage for faster file I/O
- Close unnecessary applications during batch processing

## Technical Details

### Audio Processing
- **Sample Rate**: Files are processed at 48kHz
- **Bit Depth**: Output files are 24-bit for maximum quality
- **Measurement**: ITU-R BS.1770-4 compliant LUFS measurement
- **Normalization**: Iterative loudness normalization with ±0.01 LUFS precision

### Dependencies
- **PyQt5**: User interface framework
- **pydub**: Audio file handling and format conversion
- **pyloudnorm**: Professional loudness normalization
- **numpy**: Numerical computing for audio processing
- **pygame**: Audio playback functionality

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Commit changes: `git commit -am 'Add new feature'`
4. Push to branch: `git push origin feature/new-feature`
5. Submit a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues, feature requests, or questions:
- Open an issue on [GitHub Issues](https://github.com/yourusername/unreal-audio-normalizer/issues)
- Check existing issues for solutions
- Provide detailed information including error messages and system specs

## Changelog

### Version 2.0.0
- Fixed absolute path handling for better compatibility
- Improved MP3 support with embedded FFmpeg
- Enhanced error handling and user feedback
- Added proper temporary file cleanup
- Improved configuration file management
- Better cross-system compatibility

### Version 1.0.0
- Initial release
- Basic LUFS normalization functionality
- Multiple format support
- Custom presets system