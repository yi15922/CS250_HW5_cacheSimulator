#include <stdio.h> 
#include <stdlib.h> 
#include <math.h> 
#include <string.h> 
#include <time.h>



int log2(int n) { 
    int r=0;
    while (n>>=1) r++;
    return r; 
}

typedef struct block{ 
    int tag;
    bool valid;
    clock_t time;
    char data[64];
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

    

    FILE* trace = fopen(argv[1], "r");
    int cacheSize = atoi(argv[2]); 
    int numWays = atoi(argv[3]);
    int blockSize = atoi(argv[4]);

    int numSets = cacheSize*1024/blockSize/numWays;
    int offsetBits = log2(blockSize);
    int indexBits = log2(numSets);
    int tagBits = 24-offsetBits-indexBits;
    //printf("%d way set associative, %d sets.\n", numWays, numSets);
    //printf("|-----tag: %d-------|---------index: %d--------|----block offset: %d------|\n", tagBits, indexBits, offsetBits);


    // Create the main memory of 16MB
    char* memory = (char*)malloc(16777216*sizeof(char)); 

    block** cache = (block**)malloc(numSets * sizeof(block*));

    for (int i = 0; i < numSets; i++){ 
        cache[i] = (block*)malloc(numWays * sizeof(block));
    }

    //block cache[numSets][numWays];



//  Parse the trace file
    char type[6]; 
    int addr; 
    int length; 
    while (fscanf(trace, "%s %x %d", &type, &addr, &length) != EOF){ 


        // Parse the address

        int blockOffset = lowerBits(addr, offsetBits);
        int setIndex = lowerBits(addr<<offsetBits, indexBits);
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


            // Scan the correct length of the input and write to memory
            for (int i = 0; i < length; i++){ 
                fscanf(trace, "%02hhx", &memory[addr+i]);
            }


            // Check all valid bits of set
            for (int way = 0; way < numWays; way++){ 
                //printf("valid bit %d\n", cache[setIndex][way].valid);

                // If invalid check the next one
                if (cache[setIndex][way].valid ==1) { 

                    // Increment valid count
                    validCount += 1; 

                    // If tag matches 
                    if (cache[setIndex][way].tag == tag){ 
                        // Mark hit
                        miss = 0;
                        printf("hit\n");
                        
                        // Mark access time
                        cache[setIndex][way].time = clock();


                        // Write tag
                        //printf("Tag was %d\n", blockToWrite->tag);
                        cache[setIndex][way].tag = tag;
                        //printf("New tag %d\n", blockToWrite->tag);

                        // Writing to the block from memory
                        for (int byte = 0; byte < length; byte++){  

                            // Write data from memory to block
                            cache[setIndex][way].data[byte + blockOffset] = memory[addr+byte];
                            //printf("%2hhx", blockToWrite->data[byte]);
                        }

                        break;

                    // If tag doesn't match move on to next block
                    } 
                }
            }

            // If not found at this point, don't write to block
            if (miss != 0) { 
                printf("miss\n");
                // Go through the set again to find free block
            //     for (int way = 0; way < numWays; way++){
            //         if(cache[setIndex][way].valid == 0){ 
            //             blockToWrite = &cache[setIndex][way];
            //         } else { 

            //             // Also keep track of the least recently used block
            //             if (cache[setIndex][way].time < LRU->time){ 
            //                 LRU = &cache[setIndex][way];
            //             }
            //         }
            //     }
            

            //     // If all blocks are valid (no free block)
            //     if (validCount == numWays){ 

            //         // Write to least recently used block
            //         blockToWrite = LRU;
            //     }
                
            // }

            
            // If this was not a miss, write updated memory to block
            }





        // If the instruction is a load
        } else { 
            printf("load 0x%x ", addr);

            // Check all valid bits of set
            for (int way = 0; way < numWays; way++){ 
                // If invalid check the next one
                if (cache[setIndex][way].valid == 1) { 
                    // If tag matches 
                    if (cache[setIndex][way].tag == tag){ 
                        // Mark hit
                        miss = 0;
                        printf("hit ");

                        // Mark access time
                        cache[setIndex][way].time = clock();

                        // Print data
                        for (int byte = blockOffset; byte < length+blockOffset; byte++){
                            printf("%02hhx", cache[setIndex][way].data[byte]);
                        }

                        break;


                    // If tag doesn't match move on to the next block
                    }
                }
            }

            // If already found something then go to next instruction
            if (miss == 0){ 
                printf("\n");
            // If nothing found after searching through whole set
            } else { 

                printf("miss ");

                // Go through the set again to find free block
                for (int way = 0; way < numWays; way++){
                    if(cache[setIndex][way].valid == 0){ 
                        wayToWrite = way;
                        break;

                    } else { 

                        // Also keep track of the least recently used block non-free block
                        if (cache[setIndex][way].time < cache[setIndex][LRU].time){ 
                            LRU = way;
                        }
                    }
                }


                // If all blocks are valid (no free block)

                if (validCount == numWays){ 
                    // Write to least recently used block
                    wayToWrite = LRU;
                }

                // Mark access time
                cache[setIndex][wayToWrite].time = clock();

                // Mark as valid 
                cache[setIndex][wayToWrite].valid = 1;
                //printf("wrote valid bit %d\n", cache[setIndex][wayToWrite].valid);

                // Write tag
                cache[setIndex][wayToWrite].tag = tag;

                // Writing to the block from memory
                for (int byte = 0; byte < length; byte++){  

                    // Write data from memory to block
                    cache[setIndex][wayToWrite].data[byte + blockOffset] = memory[addr+byte];
                    printf("%02hhx", cache[setIndex][wayToWrite].data[byte + blockOffset]);
                }
                printf("\n");

            }
            
        }

    }

    fclose(trace);
    return EXIT_SUCCESS;
}