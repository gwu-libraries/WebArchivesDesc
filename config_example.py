class Config:
    #ArchivesSpace
    aspace_user = '' #put aspace username here
    aspace_pass = '' #put aspace password here
    aspace_repo = ''
    aspace_host = '' #put API host URL here. Make sure you don't have a slash ('/') at the end of the URL.
    

    #Archive-It
    AI_account = "" #account number (for GW LAI)
    AI_user = '' #individual account user name
    AI_pass = ""

    #Expected Values
    subject = "Web Archives" #will look for a subject with this value as a title
    phystech_label_scrc = 'Web Archives - SCRC'
    phystech_label_ia = "Web Archives - Internet Archive"
    extent_type = "web capture(s)"

    #controlled values (to post to AOs)
    data_access_label = "Access Requirements"
    data_access_note_scrc = 'This item includes web archives data preserved in the WARC (Web ARChive) file format. To view and interact with these files, you will need to utilize web archival replay tools, like the "Wayback Machine." For alternative access or for obtaining the original WARC files, please contact the Special Collections Research Center. Please note, that WARC files may be large and difficult to work with. Requests for web archives data may take additional time to process.'
    data_access_note_ia = "Direct access to web archives data is not avalaible. This data is managed directly by the Internet Archive and can only be access via replay mechanisms like the Wayback Machine."

    acq_note_scrc = "This Web Archives data was captured by the GW Web Archives program using Internet Archive's 'Archive-it' service."
    acq_note_ia = "Web Archives data was captured by the Internet Archive, not the GW web archiving program."

