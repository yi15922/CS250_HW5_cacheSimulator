#include <stdio.h> 
#include <stdlib.h> 
#include <math.h> 

int main(int argc, char* argv[]){ 
    FILE* theFile = fopen(argv[1], "r");        // open the file
    int ppn;
    int vadd = strtol(argv[2], NULL, 16);       // read virtual address as hex

    // read the first 2 inputs for system information
    int system; 
    fscanf(theFile, "%d", &system);  
    //printf("System is %d bits\n", system);
    int pagesize;
    fscanf(theFile, "%d", &pagesize);
    //printf("Page size is %d bytes. \n", pagesize);


    int vpnBits = log2(pow(2, system)/pagesize);        // calculate bits required for page
    //printf("%d bits for vpn\n", vpnBits);
    int offsetBits = log2(pagesize);                    // calculate bits required for offset
    //printf("%d bits for offset\n", offsetBits);

    int vpn = (vadd>>offsetBits);                       // isolate virtual page number
    int offset = vadd & (int)(pow(2, offsetBits)-1);    // isolate offset

    //printf("vpn: %x\n", vpn); 
    //printf("offset: %x\n", offset); 

    int pagetable[1<<vpnBits];                          // create an array large enough for page table

    // store entire page table in array
    int counter = 0;
    while (fscanf(theFile, "%d", &ppn) != EOF){ 
        //printf("%d\n", ppn);
        pagetable[counter] = ppn;
        counter++;
    }

    ppn = pagetable[vpn];                               // lookup vpn in page table
    if (ppn == -1){ 
            printf("PAGEFAULT\n"); 
            return EXIT_SUCCESS;
    }
    //printf("%d\n", ppn);

    int padd = (ppn<<offsetBits) | offset;              // combine with offset
    printf("%x\n", padd);


    return EXIT_SUCCESS;
}