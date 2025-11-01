struct enclose
{
    struct inner
    {
        static int x;
        void f(int i);
    };
};
 
int enclose::inner::x = 1;       // definition
void enclose::inner::f(int i) {} // definition

int main()
{
    enclose::inner obj;
    obj.f(10); // A call to the function
    return 0;
}