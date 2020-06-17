#include <stdio.h> 
#include <stdlib.h> 
#include <math.h> 
#include <string.h> 
#include <time.h>

bool debug = 0;


int log2(int n) { 
    int r=0;
    while (n>>=1) r++;
    return r; 
}

typedef struct block{ 
    int tag;
    int valid;
    int access;
    char data[1024];
} block;


int lowerBits(int input, int shift){ 
    int out = input & ((1<<shift)-1);
    return out;
}

int deleteLowerBits(int input, int shift){ 
    int out = input >> shift;
    return out;
}

int replaceUpper(int input, int replace, int shift){ 
    int lower = lowerBits(input, 24-shift); 
    int upper = replace << (24-shift); 
    int out = lower|upper;    
    return out;

}


int main(int argc, char* argv[]){ 

    clock_t start = clock();

    FILE* trace = fopen(argv[1], "r");
    int cacheSize = atoi(argv[2]); 
    int numWays = atoi(argv[3]);
    int blockSize = atoi(argv[4]);
    int loopCount;

    int numSets = cacheSize*1024/blockSize/numWays;
    int offsetBits = log2(blockSize);
    int indexBits = log2(numSets);
    int tagBits = 24-offsetBits-indexBits;

    if(debug){ 
        printf("%d way set associative, %d sets.\n", numWays, numSets);
        printf("|-----tag: %d-------|---------index: %d--------|----block offset: %d------|\n", tagBits, indexBits, offsetBits);
    }

    // Create the main memory of 16MB
    char* memory = (char*)malloc(16777216*sizeof(char)); 

    block** cache = (block**)malloc(numSets * sizeof(block*));

    for (int i = 0; i < numSets; i++){ 
        cache[i] = (block*)malloc(numWays * (sizeof(block)));
    }

    //block cache[numSets][numWays];



//  Parse the trace file
    char type[6]; 
    int addr; 
    int length; 
    while (fscanf(trace, "%s %x %d", &type, &addr, &length) != EOF){ 
        
        if (debug){
            for (int i = 0; i < numSets; i++){ 
                printf("Set: %d \t", i);
                for (int j = 0; j < numWays; j++){ 
                    printf("%d %d:%d ", j, cache[i][j].tag, cache[i][j].valid);
                }
                printf("\n");
            }
        }

        // Parse the address

        if(debug){ 
            printf("\n----------------------------------------------------------\n");
        }

        

        int blockOffset = lowerBits(addr, offsetBits);
        int setIndex = lowerBits(addr>>offsetBits, indexBits);
        int tag = addr>>(24-tagBits);

        // Miss by default
        bool miss = 1;

        int validCount = 0;

        int wayToWrite; 
        int LRU = 0; 


        //printf("Set %d, block offset %d, tag = %d\n", setIndex, blockOffset, tag);

        //printf("%x, %d\n", addr, length);
        // If the instruction is a store
        if (!strcmp(type, "store")){ 

            printf("store 0x%x ", addr);

            if (debug){
            printf("\nStoring to memory address %2x\n", addr);
            printf("Set 0 way 1 %d:%d ", cache[0][1].tag, cache[0][1].valid);
            }

            // Scan the correct length of the input and write to memory
            for (int i = 0; i < length; i++){ 
                fscanf(trace, "%02hhx", &memory[addr+i]);
                //printf("\t Memory: %2hhx\n", memory[addr+i]);
            }


            // Check all valid bits of set
            for (int way = 0; way < numWays; way++){ 
                //printf("valid bit %d\n", cache[setIndex][way].valid);

                // If invalid check the next one
                if (debug){
                    printf("Set 0 way 1 %d:%d ", cache[0][1].tag, cache[0][1].valid);

                    printf("\n Store: searching set %d way %d valid bit: %d tag %d \toffset %d\n", setIndex, way, cache[setIndex][way].valid, cache[setIndex][way].tag, blockOffset);
                }
                if (cache[setIndex][way].valid == 1) { 
                    
                    // Increment valid count
                    validCount += 1; 
                    if (debug){
                        printf("Set 0 way 1 %d:%d ", cache[0][1].tag, cache[0][1].valid);

                        printf("\nValid. Found tag: %d, my tag: %d", cache[setIndex][way].tag, tag);
                    }
                    // If tag matches 
                    if (cache[setIndex][way].tag == tag){ 
                        if (debug){
                            printf("Set 0 way 1 %d:%d ", cache[0][1].tag, cache[0][1].valid);
                            printf("\nFound match\n");
                        }
                        // Mark hit
                        miss = 0;
                        printf("hit\n");
                        
                        wayToWrite = way;
                        // Mark access time
                        cache[setIndex][wayToWrite].access = loopCount;
                        //printf("\nUpdated way %d access time %d\n", way, cache[setIndex][way].access);

                        // Writing entire block from memory
                        if (debug){
                            printf("\nWriting to set %d way %d from memory\n", setIndex, wayToWrite);
                            printf("Set 0 way 1 %d:%d ", cache[0][1].tag, cache[0][1].valid);
                        }
                        for (int byte = 0; byte < blockSize; byte++){  
                            cache[setIndex][wayToWrite].data[byte] = memory[addr-blockOffset+byte];
                            //printf("%2hhx", cache[setIndex][way].data[byte+blockOffset]);
                        }
                        if (debug){ 
                            printf("\nWrote %d bytes to memory\n", blockSize);
                            printf("Set 0 way 1 %d:%d ", cache[0][1].tag, cache[0][1].valid);
                        }

                        break;

                    // If tag doesn't match move on to next block
                    } 
                }
            }

            // printf("\n%d blocks are valid\n", validCount);


            // If not found at this point, don't write to block
            if (miss != 0) { 
                printf("miss\n");
    
            }





        // If the instruction is a load
        } else { 
            printf("load 0x%x ", addr);

            // Check all valid bits of set
            for (int way = 0; way < numWays; way++){ 

                if (debug){
                printf("\n Load: searching set %d way %d valid bit: %d tag %d \t offset %d\n", setIndex, way, cache[setIndex][way].valid, cache[setIndex][way].tag, blockOffset);
                }

                // If invalid check the next one
                if (cache[setIndex][way].valid == 1) { 
                    // If tag matches 
                    validCount += 1;


                    if (debug){
                    printf("\nValid. Found tag: %d, my tag: %d\n", cache[setIndex][way].tag, tag);
                    }
                    if (cache[setIndex][way].tag == tag){ 
                        

                        // Mark hit
                        miss = 0;
                        printf("hit ");

                        wayToWrite = way;

                        // Mark access time
                        cache[setIndex][wayToWrite].access = loopCount;
                        // printf("\nUpdated way %d accessed time %ld\n", way, cache[setIndex][way].access);


                        // Print data
                        for (int byte = blockOffset; byte < length+blockOffset; byte++){
                            printf("%02hhx", cache[setIndex][wayToWrite].data[byte]);
                        }

                        break;


                    // If tag doesn't match move on to the next block
                    }
                }
            }

            // printf("\n%d blocks are valid\n", validCount);


            // If already found something then go to next instruction
            if (miss == 0){ 
                printf("\n");
            // If nothing found after searching through whole set
            } else { 

                printf("miss ");
                // Go through the set again to find free block
                for (int way = 0; way < numWays; way++){

                    if(debug){
                    printf("\nChecking if free set %d way %d\n", setIndex, way);
                    }

                    if(cache[setIndex][way].valid == 0){ 
                        if (debug){
                        printf("Found free block at set %d, way %d\n", setIndex, way);
                        }
                        wayToWrite = way;
                        if (debug){
                        printf("\nSet wayToWrite to %d\n", way);
                        }
                        break;

                    } else { 
                        if (debug){ 
                        printf("\nSet %d way %d is not free\n", setIndex, way);
                        }
                        // Also keep track of the least recently used block non-free block
                        if (cache[setIndex][way].access < cache[setIndex][LRU].access){ 
                            // printf("\nWay %d accessed at %d, way %d accessed at %ld, \n", way, cache[setIndex][way].access, LRU, cache[setIndex][LRU].access); 
                            // printf("\n way %d was less recent. Replacing LRU\n", way);
                            LRU = way;
                            if(debug){
                            printf("\nUpdated LRU to %d\n", LRU);
                            }
                        }
                    }
                }


                // If all blocks are valid (no free block)

                if (validCount == numWays){ 
                    // printf("\nAll blocks were valid, using LRU %d\n", LRU);
                    // Write to least recently used block
                    if (debug){ 
                    printf("\nAll blocks were valid, using LRU %d\n", LRU);
                    }
                    wayToWrite = LRU;
                }

                // Mark access time
                cache[setIndex][wayToWrite].access = loopCount;
                // printf("\nUpdated access time of way %d to %d\n", wayToWrite, cache[setIndex][wayToWrite].access);

                // Mark as valid 
                cache[setIndex][wayToWrite].valid = 1;
                if (debug){
                printf("\nValid bit is now %d\n", cache[setIndex][wayToWrite].valid);
                }

                // Write tag
                cache[setIndex][wayToWrite].tag = tag;
                if (debug){ 
                printf("\nTag is now %d\n", cache[setIndex][wayToWrite].tag = tag);
                }

                if(debug){ 
                    for (int i = 0; i < length; i++){ 
                        printf("\t Memory: %2hhx\n", memory[addr+i]);
                    }
                }

                // Writing entire block from memory
                if (debug){
                printf("\nWriting to set %d way %d from memory\n", setIndex, wayToWrite);
                }
                for (int byte = 0; byte < blockSize; byte++){  
                    cache[setIndex][wayToWrite].data[byte] = memory[addr-blockOffset+byte];
                }

                // Print only requested blocks
                for (int byte = blockOffset; byte < blockOffset + length; byte++){
                    printf("%02hhx", cache[setIndex][wayToWrite].data[byte]);

                }
                printf("\n");

            }
            
        }

        loopCount++;
    }

    fclose(trace);
    return EXIT_SUCCESS;
}