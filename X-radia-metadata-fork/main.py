def main():
    if not check_admin():
        user_input = get_user_input("Continue anyway? (y/n): ", ['y', 'n'])
        if user_input != 'y':
            print("Exiting...")
            return

    # Load configuration
    config = WatchConfig()
    
    # Ask for mode
    mode = get_user_input(
        "\nSelect mode:\n1. Manual processing\n2. Watch mode\n3. Configure watch mode\nEnter (1/2/3): ",
        ['1', '2', '3']
    )
    
    if mode == '3':
        setup_watch_config()
        return
    
    if mode == '2':
        if not config.config['watch_mode_enabled']:
            print("\nWatch mode is not configured! Please configure first.")
            return
        
        # Ask about GitHub integration
        if not config.config['github_enabled']:
            use_github = get_user_input(
                "\nWould you like to enable GitHub integration? (y/n): ",
                ['y', 'n']
            ) == 'y'
            
            if use_github:
                # Get GitHub credentials
                token = raw_input("\nEnter GitHub Personal Access Token: ").strip()
                repo_owner = raw_input("Enter GitHub repository owner: ").strip()
                repo_name = raw_input("Enter GitHub repository name: ").strip()
                branch = raw_input("Enter branch name (default: main): ").strip() or 'main'
                
                config.enable_github(token, repo_owner, repo_name, branch)
                print("\nGitHub integration configured!")
        
        # Initialize processor with watch directory output
        processor = TXRMProcessor(output_dir=config.config['cumulative_csv_path'])
        
        # Start file watcher
        watcher = TXRMFileWatcher(processor, config)
        watcher.watch()
        return
    
    # Manual mode
    search_path = raw_input("\nEnter folder path containing TXRM files: ").strip('"')
    while not os.path.exists(search_path):
        print("Path does not exist!")
        search_path = raw_input("Enter a valid folder path: ").strip('"')
    
    # Initialize processor
    processor = TXRMProcessor(output_dir=os.path.join(search_path, "metadata_output"))
    
    # Process files
    include_drift = get_user_input("\nInclude drift files? (y/n): ", ['y', 'n']) == 'y'
    txrm_files = processor.find_txrm_files(search_path, include_drift)
    
    if not txrm_files:
        print("\nNo TXRM files found in the specified path.")
        return
    
    process_mode = get_user_input(
        "\nChoose processing mode:\n1. Process all files (batch)\n2. Confirm each file\nEnter (1/2): ",
        ['1', '2']
    )
    
    for i, file_path in enumerate(txrm_files, 1):
        print("\nFile {0} of {1}:".format(i, len(txrm_files)))
        print(file_path)
        
        if process_mode == '2':
            if not _handle_interactive_mode(file_path):
                break
        
        processor.process_single_file(file_path)
    
    print("\nProcessing complete!")

if __name__ == "__main__":
    main() 