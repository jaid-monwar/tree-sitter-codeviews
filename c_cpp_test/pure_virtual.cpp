#include <iostream>
using namespace std;

class tester
{
    public:
    int x = 0;
    int func(int a, int b) {
        return a+b;
    }
};

class Base
{
  public:
  
    // Pure virtual function
    virtual void display() = 0;

    // Pure virtual destructor
    virtual ~Base() = 0;
};

// Definition of pure virtual destructor
Base::~Base()
{
    cout << "Base destructor called" << endl;
}

class Derived : public Base
{
  public:
    void display() override
    {
        cout << "Derived class display" << endl;
    }

    ~Derived()
    {
        cout << "Derived destructor called" << endl;
    }
};

int main()
{
    int x = 0;
    Base *basePtr;
    Derived derivedObj;
    basePtr = &derivedObj;
    basePtr->display();
    return 0;
}