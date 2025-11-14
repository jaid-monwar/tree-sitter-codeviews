import os
import sys
os.system("rm -rf ./dotfiles")
os.system("rm ./pngfiles/*.png")

# print("Enter filename:")
# filename = input()
filename = sys.argv[1]

os.system(f"joern-parse ./{filename}")
os.system("joern-export --repr cfg --out ./dotfiles")

filelist = os.listdir("./dotfiles")

for i in range(len(filelist)):
    os.system(f"dot -Tpng ./dotfiles/{filelist[i]} -o ./pngfiles/out{i}.png")