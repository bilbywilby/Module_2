import os
import sys
import yaml
import logging
import tempfile
from lxml import etree

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

def load_config(config_path='config.yaml'):
    """Loads filter rules from YAML."""
    if not os.path.exists(config_path):
        logging.error(f"Configuration file not found: {config_path}")
        sys.exit(1)
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_excluded_channel_ids(input_file, exclude_names):
    """
    Phase 1: Rapidly scan the <channel> block to map 
    excluded display names to their channel IDs.
    Returns a set of IDs to ignore.
    """
    excluded_ids = set()
    # Normalize exclude names for case-insensitive comparison if needed
    exclude_names_lower = {name.lower() for name in exclude_names}
    
    logging.info("Phase 1: Identifying excluded channel IDs...")
    
    context = etree.iterparse(input_file, events=('end',), tag='channel')
    
    for event, elem in context:
        display_names = elem.xpath('display-name')
        channel_id = elem.get('id')
        
        if channel_id:
            # Check if any display name matches the exclusion list
            for dn in display_names:
                if dn.text and dn.text.lower() in exclude_names_lower:
                    excluded_ids.add(channel_id)
                    logging.debug(f"Marked channel '{channel_id}' for exclusion (Match: {dn.text})")
                    break
        
        # Clear element to free memory immediately
        elem.clear()
        # Also eliminate now-empty references from the root node
        while elem.getprevious() is not None:
            del elem.getparent()[0]
            
    logging.info(f"Phase 1 Complete. {len(excluded_ids)} channels marked for exclusion.")
    return excluded_ids

def transform_xml(input_file, output_file, excluded_ids):
    """
    Phase 2: Stream the XML, writing only valid elements to a temp file,
    then atomically replace the output.
    """
    logging.info(f"Phase 2: Transforming {input_file} -> {output_file}")
    
    # Create temp file in the same directory to ensure atomic rename works across filesystems
    output_dir = os.path.dirname(output_file) or '.'
    fd, temp_path = tempfile.mkstemp(dir=output_dir, suffix='.xml')
    
    try:
        with os.fdopen(fd, 'wb') as f_out:
            # Write XML Declaration
            f_out.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
            
            # Start root element manually since we are filtering children
            # We assume the root is <tv> based on standard EPG formats. 
            # If dynamic root is needed, we'd parse the start event first.
            f_out.write(b'<tv>\n')
            
            # Stream the whole document, filtering specific tags
            context = etree.iterparse(input_file, events=('start', 'end'))
            
            skip_depth = 0 # Track depth if we are inside an excluded element
            
            for event, elem in context:
                if event == 'start':
                    # Check if this element should be skipped
                    if elem.tag == 'channel' and elem.get('id') in excluded_ids:
                        skip_depth = 1
                        continue
                    elif elem.tag == 'programme' and elem.get('channel') in excluded_ids:
                        skip_depth = 1
                        continue
                    
                    # If we are already skipping a parent, increment depth
                    if skip_depth > 0:
                        skip_depth += 1
                        continue
                    
                    # Write start tag
                    # etree.tostring writes the whole element if we aren't careful.
                    # For streaming write, we construct the tag manually or use a custom writer.
                    # Simplified approach for robustness: Write start tag manually
                    attrs = ' '.join(f'{k}="{v}"' for k, v in elem.attrib.items())
                    tag_str = f"<{elem.tag} {attrs}>" if attrs else f"<{elem.tag}>"
                    f_out.write(tag_str.encode('utf-8'))
                    
                elif event == 'end':
                    if skip_depth > 0:
                        skip_depth -= 1
                        # Clear memory
                        elem.clear()
                        while elem.getprevious() is not None:
                            del elem.getparent()[0]
                        continue
                    
                    # Write end tag
                    # Handle self-closing tags logic if needed, but EPG usually has content
                    # If element has no children and no text, it might be self-closing, 
                    # but standard XML writers usually close explicitly.
                    f_out.write(f"</{elem.tag}>".encode('utf-8'))
                    
                    # Clear memory
                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]
            
            # Close root element
            f_out.write(b'\n</tv>\n')
            
        # Atomic Replace
        os.replace(temp_path, output_file)
        logging.info("Transformation successful. Output written atomically.")
        
    except Exception as e:
        # Cleanup temp file on failure
        if os.path.exists(temp_path):
            os.remove(temp_path)
        logging.error(f"Transformation failed: {e}")
        raise

def main():
    # Paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, 'config.yaml')
    input_file = os.path.join(base_dir, 'guide.xml')
    output_file = os.path.join(base_dir, 'guide_filtered.xml')
    
    # Validation
    if not os.path.exists(input_file):
        logging.error(f"Input file not found: {input_file}")
        sys.exit(1)
        
    # Load Config
    config = load_config(config_path)
    exclude_names = config.get('filter', {}).get('exclude_channels', [])
    
    if not exclude_names:
        logging.warning("No exclusion rules found in config. Copying raw file.")
        # Fallback: simple copy could be done, but we run transform for consistency
        excluded_ids = set()
    else:
        # Phase 1
        excluded_ids = get_excluded_channel_ids(input_file, exclude_names)
    
    # Phase 2
    if not excluded_ids:
        logging.info("No channels to exclude based on config. Generating clean copy.")
    
    transform_xml(input_file, output_file, excluded_ids)

if __name__ == "__main__":
    main()
