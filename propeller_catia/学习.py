print("HELLO,PYCHARM")
message = "你好，世界"
print(message)
print(type(message))
age = 18
print(message, age)
print(type(message),type(age))
pi=3.14
print(type(pi))
is_student = True
print(type(is_student))
print(type(message),type(age),type(pi),type(is_student))
fruits = ["apple", "banana", "cherry"]
fruits[0]="banana"
print(fruits[0])
print(fruits[2])
fruits.append("orange")
print(fruits)
fruits_tuple = ("apple", "banana", "cherry")
print(fruits_tuple)
for f in fruits_tuple:
    print(f)
for i in range(10):
    print(i**2)
num = [1,2,3,4,5]
total = 0
for i in num:
    total += i
    print(total)
age = 14
if age >= 18:
    print('成年')
else:
    print('未成年')
person = {
    'name':'王小二',
    'age':'24',
'city' : '上海'
}
print(person)
print(person['name'])
def hello():
    return 'hello world'
print(hello())


