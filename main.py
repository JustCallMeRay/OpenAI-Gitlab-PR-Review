import os
import json
import requests
from flask import Flask, request
import openai

app = Flask(__name__)
#openai.api_key = "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"
#gitlab_token = "2ZbZzgZPz9o_F7kfXusx"
#gitlab_url = "https://git.facha.dev/api/v4"
openai.api_key = os.environ.get("OPENAI_API_KEY")
gitlab_token = os.environ.get("GITLAB_TOKEN")
gitlab_url = os.environ.get("GITLAB_URL")
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get("X-Gitlab-Token") != os.environ.get("EXPECTED_GITLAB_TOKEN"):
        return "Unauthorized", 403
    payload = request.json
    if payload.get("object_kind") == "merge_request":
        project_id = payload["project"]["id"]
        mr_id = payload["object_attributes"]["iid"]
        changes_url = f"{gitlab_url}/projects/{project_id}/merge_requests/{mr_id}/changes"

        headers = {"Private-Token": gitlab_token}
        response = requests.get(changes_url, headers=headers)
        mr_changes = response.json()

        diffs = [change["diff"] for change in mr_changes["changes"]]

        pre_prompt = "As a senior developer, review the following code changes and answer code review questions about them. The code changes are provided as git diff strings:"
        questions = "\n\nQuestions:\n1. Can you summarise the changes in a succinct bullet point list\n2. In the diff, are the added or changed code written in a clear and easy to understand way?\n3. Does the code use comments, or descriptive function and variables names that explain what they mean?\n4. based on the code complexity of the changes, could the code be simplified without breaking its functionality? if so can you give example snippets?\n5. Can you find any bugs, if so please explain and reference line numbers?\n6. Do you see any code that could induce security issues?\n"

        messages = [
            {"role": "system", "content": "You are a senior developer reviewing code changes."},
            {"role": "user", "content": f"{pre_prompt}\n\n{''.join(diffs)}{questions}"},
            {"role": "assistant", "content": "Format the response so it renders nicely in GitLab, with nice and organized markdown (use code blocks if needed), and send just the response no comments on the request, when answering include a short version of the question, so we know what it is."},
        ]

        completions = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            temperature=0.7,
            stream=False,
            messages=messages
        )

        answer = completions.choices[0].message["content"].strip()
        answer+="\n\nFor reference, i was given the following questions: \n"
        for question in questions.split("\n"):
            answer+=f"\n{question}"
        answer+="\n\nThis comment was generated by an artificial intelligence duck."
        print(answer)
        comment_url = f"{gitlab_url}/projects/{project_id}/merge_requests/{mr_id}/notes"
        comment_payload = {"body": answer}
        comment_response = requests.post(comment_url, headers=headers, json=comment_payload)

    return "OK", 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)