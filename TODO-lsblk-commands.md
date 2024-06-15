Commands
-------------------------------------------------------

lsblk -a -bDz -Jlo PATH,...
lsblk -aS -nJlo PATH # Get SCSI devices only

     ... = PATH,MAJ:MIN,FSVER ,UUID,FSTYPE ,FSSIZE,FSUSED,FSAVAIL
(-v) ... = ^+ KNAME,

maybe?
- FSUSE%

what's this??
- FSROOTS
- FSVER

----------

Notes:
- PATH is `id`
- parse MAJ:MIN into its parts

----------

-o NAME,FSTYPE,FSVER,LABEL,UUID,FSAVAIL,FSUSE%,MOUNTPOINTS,SIZE,OWNER,GROUP,MODE
[needs root if no udev support]
[may need to run `udevadm settle` first]

All outputs (so far)
-------------------------------------------------------

PATH,MAJ:MIN,FSVER,VENDOR,MODEL,SERIAL,REV,TYPE,FSTYPE,PTTYPE,PARTTYPE,PARTTYPENAME,UUID,LABEL,PTUUID,PARTUUID,PARTLABEL,PARTFLAGS,RA,RO,RM,HOTPLUG,TRAN,SIZE,FSSIZE,FSUSED,FSAVAIL,FSROOTS,MOUNTPOINTS,OWNER,GROUP,MODE,STATE,PHY-SEC,LOG-SEC,MIN-IO,OPT-IO,RQ-SIZE,KNAME,WWN,ALIGNMENT,ROTA,DISC-ALN,DISC-GRAN,DISC-MAX,DISC-ZERO,RAND,SCHED

What I get when running `lsblk` with the above outputs
-------------------------------------------------------

{
  "path": "/dev/ram0",
  "maj:min": "1:0",
  "fsver": null,
  "vendor": null,
  "model": null,
  "serial": null,
  "rev": null,
  "type": "disk",
  "tran": null,
  "ptuuid": null,
  "pttype": null,
  "fstype": null,
  "uuid": null,
  "label": null,
  "partuuid": null,
  "partlabel": null,
  "partflags": null,
  "ra": 128,
  "rota": false,
  "size": 67108864,
  "fssize": null,
  "fsused": null,
  "fsavail": null,
  "rm": false,
  "hotplug": false,
  "owner": "root",
  "group": "disk",
  "mode": "brw-rw----",
  "ro": false,
  "phy-sec": 4096,
  "log-sec": 512,
  "min-io": 4096,
  "opt-io": 0,
  "rq-size": 128,
  "disc-aln": 0,
  "disc-gran": 0,
  "disc-max": 0,
  "disc-zero": false,
  "fsroots": [
    null
  ],
  "mountpoints": [
    null
  ],
  "state": null,
  "rand": false,
  "kname": "ram0",
  -----
  "wwn": null,
  "alignment": 0,
  "sched": null
  ----- ??
  "parttype": null,
  "parttypename": null,
}

Working manifest
-------------------------------------------------------

@tool(
  command: lsblk
  description: List block devices
) {
  @query(
    command: """lsblk -a -bDz -Jlo NAME,PATH,MAJ:MIN,FSVER,VENDOR,MODEL,SERIAL,REV,TYPE,FSTYPE,PTTYPE,PARTTYPE,PARTTYPENAME,UUID,LABEL,PTUUID,PARTUUID,PARTLABEL,PARTFLAGS,RA,RO,RM,HOTPLUG,TRAN,SIZE,FSSIZE,FSUSED,FSAVAIL,FSROOTS,MOUNTPOINTS,OWNER,GROUP,MODE,STATE,PHY-SEC,LOG-SEC,MIN-IO,OPT-IO,RQ-SIZE,KNAME,WWN,ALIGNMENT,ROTA,DISC-ALN,DISC-GRAN,DISC-MAX,DISC-ZERO,RAND,SCHED"""
    parse: """
      fromjson
      | .blockdevices
      | map({
        # Entity Hierarchy:
        #   Device > Block > Partition Table > Partition > Filesystem

        # Block Attachment (ie. as identified by this system)
        id:                       (."maj:min"), # Abstract "device:block"

        # Device
        deviceAttachmentId:       (."maj:min" | split(":")[0]),
        deviceIsRemovable:        ([.rm, .hotplug] | any),
          # Optional
        deviceId:                 (.wwn),
        deviceSerial:             (.serial),
        deviceRevision:           (.rev),
        deviceModel:              (.model),
        deviceVendor:             (.vendor),
          # Hardware Sizes
        deviceRequestQueueSize:   (."rq-size"),
        devicePhysicalSectorSize: (."phy-sec"),
        deviceLogicalSectorSize:  (."log-sec"),
        deviceMinimumIOSize:      (."min-io"),
        deviceOptimalIOSize:      (."opt-io"), # sometimes reports 0
          # Trim (ie. active garbage collection; only some devices)
            # What does this mean ???
        deviceTrimAlignment:      (."disc-aln"),
        deviceTrimGranularity:    (."disc-gran"), # bytes; usually the physical sector size, but can be larger
        deviceTrimMaxBytes:       (."disc-max"),  # bytes; maximum unmappable bytes for drive; see: https://www.jeffgeerling.com/blog/2020/enabling-trim-on-external-ssd-on-raspberry-pi
        deviceTrimDoesZeroFill:   (."disc-zero"), # reports if device zero-fills on trim; some filesystems require this
          # Misc
        deviceIsEntropySource:    (.rand),

        # Block (Part of Device)
        blockAttachmentId:        (."maj:min" | split(":")[1]),
            # Does this have an ID?
        blockName:                (.name),  # eg. "nvme1n1"
        blockKernelName:          (.kname), # eg. "nvme1n1" (sometimes != name)
        blockPath:                (.path),  # eg. "/dev/nvme1n1"
        blockType:                (.type),  # eg. "loop", "disk", "part"ition
          # Size
        blockSize:                (.size),
          # Performance
            # not the total size in bytes - it is multiplied by some block size??
        blockReadAheadSize:       (.ra),
        blockIsRotationalDisk:    (.rota),
          # Optional (disk only)
        blockState:               (.state), # eg. "running" (HDD), "live" (SSD)
          # Optional (disk/part only)
        blockTransportType:       (.tran),
          # Permissions
        blockIsReadOnly:          (.ro),
        blockFileOwner:           (.owner),
        blockFileGroup:           (.group),
        blockFilePermissions:     (.mode),

        # Partition Table (disk/part only)
        partitionTableId:         (.ptuuid),
        partitionTableType:       (.pttype),

        # Partition (part only)
        partitionId:              (.partuuid),
        partitionName:            (.partlabel),
        partitionTypeId:          (.parttype), # needed?
        partitionTypeName:        (.parttypename),
        partitionFlags:           (.partflags), # eg. esp, boot, msftres, etc; pttype-specific

        # Filesystem (part only, if contains a filesystem)
        filesystemId:             (.uuid),
        filesystemName:           (.label),
        filesystemType:           (.fstype),
        filesystemVersion:        (.fsver),
          # Size (usually - ntfs does not have this for some reason)
        filesystemSpaceTotal:     (.fssize),
        filesystemSpaceUsed:      (.fsused),
        filesystemSpaceAvailable: (.fsavail),
          # Locations
        filesystemRootDirs:       (.fsroots),     # Where on this filesystem is considered the root directory
        filesystemMountPoints:    (.mountpoints), # Where in the system filesystem is the root directory of this filesystem attached
      })
      """
  )
  lsblk/test (hardware: block, test: 3, INCOMPLETE)
}

Semantic analysis of `lsblk` fields
-------------------------------------------------------

    ALIGNMENT  alignment offset
        WSAME  write same max bytes
        SCHED  I/O scheduler name

       PKNAME  internal parent kernel device name
         HCTL  Host:Channel:Target:Lun for SCSI
   SUBSYSTEMS  de-duplicated chain of subsystems
        ZONED  zone model
          DAX  dax-capable device

-------------##-------------------------------- ABOVE ARE UNCATEGORISED

         NAME  device name
        KNAME  internal kernel device name
         PATH  path to the device node

      MAJ:MIN  major:minor device number
           RM  removable device
      HOTPLUG  removable or hotplug device (usb, pcmcia, ...)
            ## Optional
          WWN  unique storage identifier
       SERIAL  disk serial number
          REV  device revision
        MODEL  device identifier
       VENDOR  device vendor
            ## Hardware Sizes
      RQ-SIZE  request queue size
       MIN-IO  minimum I/O size
       OPT-IO  optimal I/O size
      PHY-SEC  physical sector size
      LOG-SEC  logical sector size
            ## Trim
     DISC-ALN  discard alignment offset
    DISC-GRAN  discard granularity
     DISC-MAX  discard max bytes
    DISC-ZERO  discard zeroes data (does it zero data on discard/trim?)
            ## Misc
         RAND  adds randomness

      MAJ:MIN  major:minor device number
         TYPE  device type
             ## Size
         SIZE  size of the device
             ## Performance
         ROTA  rotational device
           RA  read-ahead of the device
             ## Optional (disk only)
        STATE  state of the device
             ## Optional (disk/part only)
         TRAN  device transport type
             ## Permissions
           RO  read-only device
        OWNER  user name
        GROUP  group name
         MODE  device node permissions

       PTUUID  partition table identifier (usually UUID)
       PTTYPE  partition table type

     PARTUUID  partition UUID
    PARTLABEL  partition LABEL
     PARTTYPE  partition type code or UUID
 PARTTYPENAME  partition type name
    PARTFLAGS  partition flags

         UUID  filesystem UUID
        LABEL  filesystem LABEL
       FSTYPE  filesystem type
        FSVER  filesystem version
             ## Size
       FSSIZE  filesystem size
       FSUSED  filesystem size used
      FSAVAIL  filesystem size available
             ## Locations
      FSROOTS  mounted filesystem roots
  MOUNTPOINTS  all locations where device is mounted

Categorisation of `lsblk` fields
-------------------------------------------------------

- This is out of date now - see the working manifest above.
- However, this does show what I would suggest to include in different levels of
  verbosity.

# Versions
PATH,MAJ:MIN,FSVER
# Types
,VENDOR,MODEL,SERIAL,REV
,TYPE,FSTYPE
,PTTYPE
,PARTTYPE,PARTTYPENAME
# IDs
,UUID,LABEL
,PTUUID
,PARTUUID,PARTLABEL
## NOTE: merge RM and HOTPLUG (just do a logical OR of them - both 0 or 1)
,PARTFLAGS,RA,RO,RM,HOTPLUG
,TRAN
# Space
,SIZE,FSSIZE,FSUSED,FSAVAIL
# Locations
,FSROOTS,MOUNTPOINTS
# Permissions
,OWNER,GROUP,MODE
# State
,STATE

# Verbose (-v)
# Access
,PHY-SEC,LOG-SEC
,MIN-IO,OPT-IO
,RQ-SIZE

# Very verbose (-vv)
# IDs
,KNAME,WWN
,ALIGNMENT,ROTA
# Trim (SSDs only)
,DISC-ALN,DISC-GRAN,DISC-MAX,DISC-ZERO
# Misc
,RAND
,SCHED

# Very very verbose (-vvv) = all
# Unknown (don't know what they're for)
,ZONED
,DAX
,WSAME
,PKNAME
,HCTL
,SUBSYSTEMS

Available output columns (`lsblk --help`)
-------------------------------------------------------

         NAME  device name
        KNAME  internal kernel device name
         PATH  path to the device node
      MAJ:MIN  major:minor device number
      FSAVAIL  filesystem size available
       FSSIZE  filesystem size
       FSTYPE  filesystem type
       FSUSED  filesystem size used
       FSUSE%  filesystem use percentage
      FSROOTS  mounted filesystem roots
        FSVER  filesystem version
   MOUNTPOINT  where the device is mounted
  MOUNTPOINTS  all locations where device is mounted
        LABEL  filesystem LABEL
         UUID  filesystem UUID
       PTUUID  partition table identifier (usually UUID)
       PTTYPE  partition table type
     PARTTYPE  partition type code or UUID
 PARTTYPENAME  partition type name
    PARTLABEL  partition LABEL
     PARTUUID  partition UUID
    PARTFLAGS  partition flags
           RA  read-ahead of the device
           RO  read-only device
           RM  removable device
      HOTPLUG  removable or hotplug device (usb, pcmcia, ...)
        MODEL  device identifier
       SERIAL  disk serial number
         SIZE  size of the device
        STATE  state of the device
        OWNER  user name
        GROUP  group name
         MODE  device node permissions
    ALIGNMENT  alignment offset
       MIN-IO  minimum I/O size
       OPT-IO  optimal I/O size
      PHY-SEC  physical sector size
      LOG-SEC  logical sector size
         ROTA  rotational device
        SCHED  I/O scheduler name
      RQ-SIZE  request queue size
         TYPE  device type
     DISC-ALN  discard alignment offset
    DISC-GRAN  discard granularity
     DISC-MAX  discard max bytes
    DISC-ZERO  discard zeroes data (ie. "does it zero-fill sectors on discard/trim?")
        WSAME  write same max bytes
          WWN  unique storage identifier
         RAND  adds randomness
       PKNAME  internal parent kernel device name
         HCTL  Host:Channel:Target:Lun for SCSI
         TRAN  device transport type
   SUBSYSTEMS  de-duplicated chain of subsystems
          REV  device revision
       VENDOR  device vendor
        ZONED  zone model
          DAX  dax-capable device

Parse
-------------------------------------------------------

parse: fromjson | .blockdevices[]

Output format
-------------------------------------------------------

$ lsblk -I 8,259 -o NAME,FSTYPE,MOUNTPOINT -JT
{
   "blockdevices": [
      {
         "name": "sda",
         "fstype": null,
         "mountpoint": null,
         "children": [
            {
               "name": "sda1",
               "fstype": null,
               "mountpoint": null
            },{
               "name": "sda2",
               "fstype": "ntfs",
               "mountpoint": null
            }
         ]
      },{
         "name": "sdb",
         "fstype": null,
         "mountpoint": null,
         "children": [
            {
               "name": "sdb1",
               "fstype": "ext4",
               "mountpoint": "/media/bluebells/Linux_storage"
            }
         ]
      },{
         "name": "nvme0n1",
         "fstype": null,
         "mountpoint": null,
         "children": [
            {
               "name": "nvme0n1p1",
               "fstype": "vfat",
               "mountpoint": "/boot/efi"
            },{
               "name": "nvme0n1p2",
               "fstype": "ext2",
               "mountpoint": "/"
            },{
               "name": "nvme0n1p3",
               "fstype": "ext4",
               "mountpoint": "/home"
            }
         ]
      },{
         "name": "nvme1n1",
         "fstype": null,
         "mountpoint": null,
         "children": [
            {
               "name": "nvme1n1p1",
               "fstype": null,
               "mountpoint": null
            },{
               "name": "nvme1n1p2",
               "fstype": "ntfs",
               "mountpoint": null
            }
         ]
      }
   ]
}

Other commands
-------------------------------------------------------

findmnt
blkid
