#!/usr/bin/env python3


# Usage:
#     python main.py                  
#     python main.py --camera 1       
#     python main.py --output mydir   
#     python main.py --duration 15    
#     python main.py --port 8080      
#     python main.py --fps 24         


import argparse
import threading


def main():
    parser = argparse.ArgumentParser(
        description="Steamic - Camera AI Motion Detection & Custom Video Codec"
    )
    parser.add_argument(
        "--camera", type=int, default=0,
        help="Camera device index (default: 0)"
    )
    parser.add_argument(
        "--output", type=str, default="clips",
        help="Output directory for recorded clips (default: clips)"
    )
    parser.add_argument(
        "--duration", type=int, default=30,
        help="Clip duration in seconds (default: 30)"
    )
    parser.add_argument(
        "--cooldown", type=int, default=5,
        help="Seconds to wait between recordings (default: 5)"
    )
    parser.add_argument(
        "--fps", type=int, default=30,
        help="Target recording framerate (default: 30)"
    )
    parser.add_argument(
        "--port", type=int, default=3400,
        help="Web UI port (default: 3400)"
    )

    args = parser.parse_args()

    from recorder import Recorder
    from web import create_app

    print("=" * 50)
    print("  Steamic - Camera AI Motion Detection")
    print("=" * 50)
    print(f"  Camera:    {args.camera}")
    print(f"  Output:    {args.output}/")
    print(f"  Duration:  {args.duration}s per clip")
    print(f"  Cooldown:  {args.cooldown}s between clips")
    print(f"  FPS:       {args.fps}")
    print(f"  Web UI:    http://localhost:{args.port}")
    print("=" * 50)
    print()

    recorder = Recorder(
        camera_index=args.camera,
        clip_duration=args.duration,
        output_dir=args.output,
        cooldown=args.cooldown,
        target_fps=args.fps,
    )

    app = create_app(recorder, clips_dir=args.output)

    
    flask_thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=args.port, threaded=True),
        daemon=True,
    )
    flask_thread.start()

    
    try:
        recorder.start()
    except KeyboardInterrupt:
        pass
    finally:
        recorder.stop()
        print("\n[Main] Stopped")


if __name__ == "__main__":
    main()
