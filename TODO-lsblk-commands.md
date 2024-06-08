Commands
-------------------------------------------------------

lsblk -a -bDz -Jlo PATH,...
lsblk -aS -nJlo PATH # Get SCSI devices only

     ... = PATH,MAJ:MIN ,UUID,FSTYPE ,FSSIZE,FSUSED,FSAVAIL
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
    DISC-ZERO  discard zeroes data
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
