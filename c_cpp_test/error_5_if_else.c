int f1() {return 1;}
int f2() {return 2;}

int main() {
    int node = 31;

    (node > 0)? f1() : f2();

    if(node == 31 || node < 0)
        printf("a");
    else if(node > 100)
        printf("b");
    else
        printf("c");

    printf("if done\n");

    switch(node){
        case 10:
            printf("10");
            break;
        case 31:
            node++;
        default:
            printf("default\n");
    }

    for(int i=0; i<node; i++) {
        node += 10;
        node /= 2;
        printf("%d\n", node);
    }
}