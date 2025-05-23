import re
from datetime import datetime
import os

def parse_error_log():
    error_lines = []
    current_error = []
    
    # Set the correct directory path
    log_file_path = os.path.join('poly-starter-code', 'error_diagnosis.log')
    output_dir = 'poly-starter-code'
    
    try:
        with open(log_file_path, 'r') as log_file:
            for line in log_file:
                # Check if line contains ERROR level
                if 'ERROR' in line:
                    # If we were collecting a previous error, add it to our list
                    if current_error:
                        error_lines.append(''.join(current_error))
                        current_error = []
                    
                    # Start collecting this error
                    current_error.append(line)
                # If we're currently collecting an error, add subsequent lines
                elif current_error:
                    current_error.append(line)
                    # If we hit a new timestamp, it's a new log entry
                    if re.match(r'\d{4}-\d{2}-\d{2}', line):
                        error_lines.append(''.join(current_error[:-1]))
                        current_error = [line]
            
            # Don't forget the last error if there is one
            if current_error:
                error_lines.append(''.join(current_error))

        # Write errors to a new file with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(output_dir, f'errors_{timestamp}.txt')
        
        with open(output_file, 'w') as error_file:
            error_file.write(f"Error Analysis Report - Generated at {datetime.now()}\n")
            error_file.write("=" * 80 + "\n\n")
            
            for error in error_lines:
                error_file.write(error)
                error_file.write("\n" + "-" * 80 + "\n\n")
            
            error_file.write(f"\nTotal errors found: {len(error_lines)}\n")
        
        print(f"Error analysis complete. Found {len(error_lines)} errors.")
        print(f"Results written to {output_file}")
        
    except FileNotFoundError:
        print(f"error_diagnosis.log file not found at {log_file_path}!")
    except Exception as e:
        print(f"An error occurred while parsing the log file: {e}")

if __name__ == "__main__":
    parse_error_log() 