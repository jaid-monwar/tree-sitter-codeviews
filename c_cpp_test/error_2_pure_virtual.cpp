#include <iostream>
using namespace std;

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
    Base *basePtr;
    Derived derivedObj;
    basePtr = &derivedObj;
    basePtr->display();
    return 0;
}