/*
 * Main source code file for lsh shell program
 *
 * You are free to add functions to this file.
 * If you want to add functions in a separate file(s)
 * you will need to modify the CMakeLists.txt to compile
 * your additional file(s).
 *
 * Add appropriate comments in your code to make it
 * easier for us while grading your assignment.
 *
 * Using assert statements in your code is a great way to catch errors early and make debugging easier.
 * Think of them as mini self-checks that ensure your program behaves as expected.
 * By setting up these guardrails, you're creating a more robust and maintainable solution.
 * So go ahead, sprinkle some asserts in your code; they're your friends in disguise!
 *
 * All the best!
 */
#include <assert.h>
#include <ctype.h>
#include <readline/readline.h>
#include <readline/history.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>


#include <sys/wait.h>
#include <sys/types.h>
#include <signal.h>


 // The <unistd.h> header is your gateway to the OS's process management facilities.
#include <unistd.h>

#include "parse.h"

static void run_cmds(Command*);
static void print_cmd(Command* cmd);
static void print_pgm(Pgm* p);
void stripwhite(char*);
char* get_firstparameter(Pgm* p);

static int is_pipeline(Pgm* p);

static void execute_command(Pgm *p);


int main(void)
{
    for (;;)
    {
        char* line;
        line = readline("> ");

        // If EOF encountered, exit shell
        if (!line)
        {
            break;
        }


        // Remove leading and trailing whitespace from the line
        stripwhite(line);

        // If stripped line not blank
        if (*line)
        {
            add_history(line);

            Command cmd;
            if (parse(line, &cmd) == 1)
            {
                run_cmds(&cmd);
            }
            else
            {
                printf("Parse ERROR\n");
            }
        }

        // Clear memory
        free(line);
    }

    return 0;
}

/* Execute the given command(s).

 * Note: The function currently only prints the command(s).
 *
 * TODO:
 * 1. Implement this function so that it executes the given command(s).
 * 2. Remove the debug printing before the final submission.
 */
static void run_cmds(Command* cmd_list)
{
    print_cmd(cmd_list);


    //If the command is “cd” and "exit", we shold not fork() child
    //process.
    if (strcmp(*(cmd_list->pgm->pgmlist), "cd") == 0)
    {
        char* path = *(++(cmd_list->pgm->pgmlist));
        chdir(path);
        return;
    }

    else if (strcmp(*(cmd_list->pgm->pgmlist), "exit") == 0)
    {
        exit(EXIT_SUCCESS);
    }



    pid_t pid = fork();
    assert(pid != -1);
    
    if (pid == 0) //child process
    {
        int fd1, fd2, fd3; //IO file description

        if (cmd_list->rstdin != NULL)
        {
            fd1 = open(cmd_list->rstdin, O_RDONLY);

            if (fd1 == -1)
            {
                perror("open() for rstdin failed");
                exit(EXIT_FAILURE);
            }

            dup2(fd1, STDIN_FILENO);
            close(fd1);
        }

        if (cmd_list->rstdout != NULL)
        {
            fd2 = open(cmd_list->rstdout, O_CREAT | O_WRONLY | O_TRUNC, S_IRWXU | S_IRWXG | S_IRWXO);

            if (fd2 == -1)
            {
                perror("open() for rstdout failed");
                exit(EXIT_FAILURE);
            }

            dup2(fd2, STDOUT_FILENO);
            close(fd2);
        }

        if (cmd_list->rstderr != NULL)
        {
            fd3 = open(cmd_list->rstderr, O_CREAT | O_WRONLY | O_APPEND, S_IRWXU | S_IRWXG | S_IRWXO);

            if (fd3 == -1)
            {
                perror("open() for rstderr failed");
                exit(EXIT_FAILURE);
            }

            dup2(fd3, STDERR_FILENO);
            close(fd3);
        }

        execute_command(cmd_list->pgm);

    }
    else //parent process
    {
        //If the command end with “&”， it means it is a background process, so the
        //parent process donnot call the wait().
        if (!cmd_list->background)
        {
            int status = 0;
            wait(&status);
        }
    }

}

static void execute_command(Pgm* current_pgm)
{
    pid_t pid = -1;
    int pipe_fds[2];

    if (current_pgm->next != NULL)
    {
        if (pipe(pipe_fds) == -1) {
            perror("pipe");
            exit(EXIT_FAILURE);
        }

        pid = fork();
        assert(pid != -1);

    }

    if (pid > 0 || is_pipeline(current_pgm) || pid == -1) //Parent process
    {

        // If there's a pipeline, redirect input from the previous command
        if (is_pipeline(current_pgm) == 0) {
            close(pipe_fds[1]);
            dup2(pipe_fds[0], STDIN_FILENO);
            close(pipe_fds[0]); // Close read end of the pipe
            wait(pid);
        }

        execvp(current_pgm->pgmlist[0], current_pgm->pgmlist);

    }
    else if (pid == 0) { // Child process

        close(pipe_fds[0]);
        dup2(pipe_fds[1], STDOUT_FILENO);

        close(pipe_fds[1]); // Close write end of the pipe

        execute_command(current_pgm->next);
    }

}


static int is_pipeline(Pgm* p) {

    if (p->next != NULL)
    {
        return 0;
    }
    else
    {
        return 1;
    }
}

/*
 * Print a Command structure as returned by parse on stdout.
 *
 * Helper function, no need to change. Might be useful to study as inpsiration.
 */
static void print_cmd(Command* cmd_list)
{
    printf("------------------------------\n");
    printf("Parse OK\n");
    printf("stdin:      %s\n", cmd_list->rstdin ? cmd_list->rstdin : "<none>");
    printf("stdout:     %s\n", cmd_list->rstdout ? cmd_list->rstdout : "<none>");
    printf("background: %s\n", cmd_list->background ? "true" : "false");
    printf("Pgms:\n");
    print_pgm(cmd_list->pgm);
    printf("------------------------------\n");
}

/* Print a (linked) list of Pgm:s.
 *
 * Helper function, no need to change. Might be useful to study as inpsiration.
 */
static void print_pgm(Pgm* p)
{
    if (p == NULL)
    {
        return;
    }
    else
    {
        char** pl = p->pgmlist;

        /* The list is in reversed order so print
         * it reversed to get right
         */
        print_pgm(p->next);
        printf("            * [ ");
        while (*pl)
        {
            printf("%s ", *pl++);
        }
        printf("]\n");
    }
}


 /* Strip whitespace from the start and end of a string.
  *
  * Helper function, no need to change.
  */
void stripwhite(char* string)
{
    size_t i = 0;

    while (isspace(string[i]))
    {
        i++;
    }

    if (i)
    {
        memmove(string, string + i, strlen(string + i) + 1);
    }

    i = strlen(string) - 1;
    while (i > 0 && isspace(string[i]))
    {
        i--;
    }

    string[++i] = '\0';
}
