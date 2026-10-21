/** @file
  DT and initrd status published by a device firmware memory driver.

  A platform driver that sets up DRAM and the boot image ramdisk from the
  device tree can install a UKE_MEM_STATUS structure under
  gUkeMemStatusGuid.  The boot manager then shows the values on its summary
  line, which makes a payload that is not found diagnosable from the menu
  without a serial port.

  Copyright (c) 2026, UniXNU contributors. All rights reserved.
  SPDX-License-Identifier: BSD-2-Clause-Patent
**/

#ifndef UKE_MEM_STATUS_H_
#define UKE_MEM_STATUS_H_

#include <Uefi.h>

#define UKE_MEM_STATUS_MAGIC    0x554B454D  // 'UKEM'
#define UKE_MEM_STATUS_VERSION  1

//
// DtbSource values.
//
#define UKE_MEM_DTB_NONE   0
#define UKE_MEM_DTB_HOB    1
#define UKE_MEM_DTB_TABLE  2

typedef struct {
  UINT32    Magic;
  UINT32    Version;
  UINT32    DtbSource;          ///< UKE_MEM_DTB_*.
  UINT32    InitrdPublished;    ///< 1 when the initrd block device was installed.
  UINT32    MemoryBanks;        ///< /memory ranges found in the DT.
  UINT32    ReservedRanges;     ///< /reserved-memory ranges found in the DT.
  UINT32    AddedRanges;        ///< DRAM ranges added to the GCD.
  UINT32    Reserved;
  UINT64    Dtb;                ///< Physical address of the DT.
  UINT64    DtbSize;
  UINT64    InitrdStart;
  UINT64    InitrdEnd;
  UINT64    AddedBytes;
  CHAR8     PanicLine[128];      ///< First line of the previous XNU panic log, or empty.
} UKE_MEM_STATUS;

extern EFI_GUID  gUkeMemStatusGuid;

#endif
