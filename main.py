""" Painting google facade """
import sys

from ortools.linear_solver import pywraplp

class Command(object):
    def __init__(self):
        self.name = None

class PaintLine(Command):
    def __init__(self, r1, c1, r2, c2):
        assert r1 == r2 or c1 == c2
        self.r1 = r1
        self.c1 = c1
        self.r2 = r2
        self.c2 = c2

    def __str__(self):
        return 'PAINT_LINE %d %d %d %d' % (self.r1, self.c1, self.r2, self.c2)

class PaintSquare(Command):
    def __init__(self, r, c, s):
        self.r = r
        self.c = c
        self.s = s

    def __str__(self):
        return 'PAINT_SQUARE %d %d %d' % (self.r, self.c, self.s)

class EraseCell(Command):
    def __init__(self, r, c):
        self.r = r
        self.c = c

    def __str__(self):
        return 'ERASE_CELL %d %d' % (self.r, self.c)

def read_image(filename):
    """ read input image """
    with open(filename) as f:
        [n, m] = [int(x) for x in f.readline().strip().split()]
        image = [[]] * n
        for i in range(n):
            line = f.readline().strip()
            assert len(line) == m
            image[i] = [0] * m
            j = 0
            for c in line:
                if c == '.':
                    image[i][j] = 0
                elif c == '#':
                    image[i][j] = 1
                else:
                    assert False
                j += 1
    return image

def print_image(image):
    """ print the initial image """
    print '%d %d' % (len(image), len(image[0]))
    for line in image:
        l = ''.join([('#' if j == 1 else '.') for j in line])
        print l

def print_solution(solution, out_filename):
    solver, commands = solution
    with open(out_filename, 'w') as f:
        print >>f, '%s' % int(solver.Objective().Value())
        for command in commands:
            if command.var.SolutionValue() == 1:
                print >>f, command

def areLineEndsWhite(image, r1, c1, r2, c2):
    return image[r1][c1] == 0 or image[r2][c2] == 0

def moreWhitesThanBlacks(image, r1, c1, r2, c2):
    if r1 == r2:
        line = image[r1][c1:c2+1]
    else:
        line = [image[i][c1] for i in range(r1, r2 + 1)]

    linePlusErases = len([1 for f in line if f == 0]) + 1
    blackPatches = 0
    currentPatch = 0
    for p in line:
        if p == 0:
            currentPatch = 0
        elif currentPatch == 0:
            currentPatch = 1
            blackPatches += 1

    return blackPatches > linePlusErases

def gen_commands(image):
    """
    returns:
    - image with each cell having a list of commands that paint it
    - list of all the commands
    """
    n, m = len(image), len(image[0])

    cellCommands = [[[] for _ in range(m)] for _ in range(n)]
    commands = []

    # Horizontal paint lines are the only commands that paint single cells

    # Generate horizontal paint lines
    for i in range(n):
        for j in range(m):
            for k in range(j, m):
                if areLineEndsWhite(image, i, j, i, k) or \
                    moreWhitesThanBlacks(image, i, j, i, k):
                    continue
                c = PaintLine(i, j, i, k)
                commands.append(c)
                for z in range(j, k + 1):
                    cellCommands[i][z].append(c)

    # Generate vertical paint lines
    for j in range(m):
        for i in range(n):
            for k in range(i + 1, n):
                if areLineEndsWhite(image, i, j, k, j) or \
                    moreWhitesThanBlacks(image, i, j, k, j):
                    continue
                c = PaintLine(i, j, k, j)
                commands.append(c)
                for z in range(i, k + 1):
                    cellCommands[z][j].append(c)

    # Generate squares
    for i in range(n):
        for j in range(m):
            e = 3
            while e + i <= n and e + j <= m:
                s = e / 2
                r = i + s
                c = j + s
                command = PaintSquare(r, c, s)
                commands.append(command)
                for r1 in range(i, i + e):
                    for c1 in range(j, j + e):
                        cellCommands[r1][c1].append(command)
                e += 2

    # Generate erases
    for i in range(n):
        for j in range(m):
            if image[i][j] == 0 and len(cellCommands[i][j]) > 0:
                c = EraseCell(i, j)
                commands.append(c)
                cellCommands[i][j].append(c)

    print 'Generated %d commands' % len(commands)

    return commands, cellCommands

def print_gen_commands(commands, cellCommands):
    """ print all possible commands """
    print '-------------------------- Commands'
    for command in commands:
        print command
    print '-------------------------- Cell commands'
    for i in range(len(cellCommands)):
        for j in range(len(cellCommands[0])):
            print '>>>>> %d %d' % (i, j)
            for c in cellCommands[i][j]:
                print c

def solve(image):
    commands, cellCommands = gen_commands(image)
    #print_gen_commands(commands, cellCommands)
    solver = pywraplp.Solver('PaintingLP',
                             pywraplp.Solver.CBC_MIXED_INTEGER_PROGRAMMING)

    for c in commands:
        var = solver.IntVar(0, 1, str(c))
        c.var = var

    print 'Generated variables'

    n, m = len(image), len(image[0])
    for i in range(n):
        for j in range(m):
            if image[i][j] == 1:
                solver.Add(solver.Sum([c.var for c in cellCommands[i][j]]) >= 1)
            elif len(cellCommands[i][j]) > 0:
                drawCommands = cellCommands[i][j][:-1]
                eraseCommand = cellCommands[i][j][-1]
                assert isinstance(eraseCommand, EraseCell)
                solver.Add(solver.Sum([c.var for c in drawCommands]) <=
                           len(drawCommands) * eraseCommand.var)

    # the number of commands cannot be larger than the number of black cells
    blackCells = 0
    for i in range(n):
        for j in range(m):
            if image[i][j] == 1:
                blackCells += 1

    solver.Add(solver.Sum([c.var for c in commands]) <= blackCells)

    print 'Generated constraints'

    objective = solver.Sum([c.var for c in commands])
    objective = solver.Minimize(objective)

    print 'Generated objective'

    solver.SetTimeLimit(20000)
    status = solver.Solve()

    print 'Solved'

    return solver, commands

def main(in_filename, out_filename):
    """ main """
    image = read_image(in_filename)
    print_image(image)
    solution = solve(image)
    print_solution(solution, out_filename)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print 'Provide the input and the output files'
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
