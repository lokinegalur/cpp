#include<iostream>
using namespace std;
void sqr1(int n){
	n*=n;
}

void sqr2(int* n){
	*n=*n*(*n);
}

void sqr3(int &n){
	n*=n;
}


int main(){
	int a=6;
	sqr1(a);
	cout<<"sqr1 "<<a<<endl;
	sqr2(&a);
	cout<<"sqr2 "<<a<<endl;
	a=6;
	sqr3(a);
	cout<<"sqr3 "<<a<<endl;
	return 0;
}