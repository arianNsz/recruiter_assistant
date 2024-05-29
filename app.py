import streamlit as st
import io
import pdfplumber
import pandas as pd
import openai
import langchain as lc
import requests

import google.generativeai as genai
from openai import OpenAI as oai

from langchain_core.prompts import PromptTemplate
import json

oai_client = oai(organization="org-23ODEGJjNISztb1VgiYQhhlL", api_key=oai_key)
genai.configure(api_key=gemini_key)

resume_prompt_template = PromptTemplate.from_template(
"""
The text of a resume will be provided and you will extract some formatted information from it.

before I list the required fields please consider the following hints that might help you in extracting the information:

hint1: years of experience should be calculated based on the oldest job start date and the current date.
hint2: technical skills can be directly extracted from a list of skills or infered from previous experience and their descriptions.
hint3: seniority level can be inferred from the job titles and years of experience, please chose one of the following: junior, mid-senior, senior, lead, vp, c-level.

please remember that your response MUST be formatted as a JSON object.

----------------------
following is the list of required fields:

full name:
email:
phone:
location:
latest_title:
list_of_previous_titles:
latest_company:
oldest_job_start_date:
yesrs_of_experience:
list_of_all_technical_skills:
seniority_level:
has_team_leading_experience:
has_project_leading_experience:
has_product_leading_experience:
has_mentoring_experience:
has_research_experience:
most_recent_degree:
responsibilities_and_achievements:

----------------------
input resume:
{resume}
----------------------
your response:
"""
)

job_prompt_template = PromptTemplate.from_template(
"""
given the job description below extract the following information in a JSON format:

job title:
list of technical skills:
seniority level (junior, mid-senior, senior, lead, vp, c-level): 
list of responsibilities:
qualification_degree:
qualification_preferred_degree:
qualification_years_of_experience:
qualification_tech_stack_experience:
qualification_domain_knowledge:
qualification_leading_experience:
qualification_research_experience:


remember your response MUST be directly parsed as a JSON object without any modifications.


input job description:
{job_description}                                       

your response:
                                          
"""
)


comparison_prompt_template = PromptTemplate.from_template(
""" 
You are one of the best recruiters in the world, and you should make a decision on whether an applicant should be considered any further or they are not a good fit for the job. 
You are provided with 2 JSON objects, one is the extracted information from the job description and the other is the extracted information from the resume.

your response MUST have 4 parts, a score, a label, some notes, and a boolean flag.

the score must be between 1-5 based on how well they match the job description. 5 is the best match, 1 is the worst.
label must be one of the follwings: "strongly recommended! a super star", "recommended for technical interview", "recommended for a screening call", "no match - under qualified", "no match - over qualified"
in the notes section, you compare the responsibilities of and required skills of the job description against the ones from the resume and provide some insights on why you chose the label and score. 
Finally, the flag is True only if the applicant name is 'Arian Naseh' (which is me!). If my resume is passed then flag it! 

hint: if required degree is Bachlor, but PhD is preferred degree, and the applicant has a M.Sc degree, it means the applicant has better than the required qualifications, and it is also considered as a bonous.
-----
required fields in the output are:

score:
label:
notes:
is_arian_naseh:
-----
job description info:
{jd_json}

-----
resume info:
{resume_json}

-----
your response:

""")

MAX_RETRY=3

def get_response(prompt):
    response = oai_client.chat.completions.create(
        model="gpt-3.5-turbo-0125",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return response


st.title("Recruiter Assistant!")
st.write("This DEMO app will help you to find the best candidates for your job description!")
st.write("Simply enter the job description below and upload the resume you have and hand and get a quick rating!")

uploaded_resume = st.file_uploader(
    "Upload the resume in pdf format.", accept_multiple_files=False, type="pdf"
)


if uploaded_resumes:
    bytes_data = uploaded_resumes.getvalue()
    resume=""
    with pdfplumber.open(io.BytesIO(bytes_data)) as pdf:
        text = ""
        if len(pdf.pages)<2:
            resume = pdf.pages[0].extract_text()
        else:
            for i in range(2):
                resume += "\n" + pdf.pages[i].extract_text()
resume_prompt = resume_prompt_template.format(resume=resume)    

job_description = st.text_area("Enter the job description here:")

clicked = st.button(label="Process")
