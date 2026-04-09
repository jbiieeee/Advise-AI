from django.core.management.base import BaseCommand
from core.models import CurriculumSubject


BSIT_SUBJECTS = [
    # ── First Year, First Semester
    {'code': 'GEC 1002', 'title': 'Readings in Philippine History', 'units': 3, 'year_level': 1, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'GEC 004',  'title': 'Mathematics in the Modern World',  'units': 3, 'year_level': 1, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'CITE 1001','title': 'Introduction to Computing',         'units': 3, 'year_level': 1, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'core', 'track': ''},
    {'code': 'CITE 002', 'title': 'Computer Programming 1',           'units': 3, 'year_level': 1, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'core', 'track': ''},
    {'code': 'MATH 022', 'title': 'Linear Algebra',                   'units': 3, 'year_level': 1, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'core', 'track': ''},
    {'code': 'PE 101',   'title': 'Physical Education 1',              'units': 2, 'year_level': 1, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'pe', 'track': ''},
    {'code': 'NSTP 001', 'title': 'National Service Training Program 1','units': 3, 'year_level': 1, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'nstp', 'track': ''},

    # ── First Year, Second Semester
    {'code': 'GEC 001',  'title': 'Understanding the Self',           'units': 3, 'year_level': 1, 'semester': '2nd', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'GEC 005',  'title': 'Purposive Communication',          'units': 3, 'year_level': 1, 'semester': '2nd', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'GEC 006',  'title': 'Art Appreciation',                 'units': 3, 'year_level': 1, 'semester': '2nd', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'MATH 025', 'title': 'Discrete Mathematics',             'units': 3, 'year_level': 1, 'semester': '2nd', 'prerequisite_codes': '', 'subject_type': 'core', 'track': ''},
    {'code': 'CITE 003', 'title': 'Computer Programming 2',           'units': 3, 'year_level': 1, 'semester': '2nd', 'prerequisite_codes': 'CITE 002', 'subject_type': 'core', 'track': ''},
    {'code': 'CITE 012', 'title': 'Introduction to Human Computer Interaction', 'units': 3, 'year_level': 1, 'semester': '2nd', 'prerequisite_codes': 'CITE 002', 'subject_type': 'core', 'track': ''},
    {'code': 'PE 102',   'title': 'Physical Education 2',             'units': 2, 'year_level': 1, 'semester': '2nd', 'prerequisite_codes': 'PE 101', 'subject_type': 'pe', 'track': ''},
    {'code': 'NSTP 002', 'title': 'National Service Training Program 2', 'units': 3, 'year_level': 1, 'semester': '2nd', 'prerequisite_codes': 'NSTP 001', 'subject_type': 'nstp', 'track': ''},

    # ── Second Year, First Semester
    {'code': 'CITE 004', 'title': 'Data Structures and Algorithm',    'units': 3, 'year_level': 2, 'semester': '1st', 'prerequisite_codes': 'CITE 003', 'subject_type': 'core', 'track': ''},
    {'code': 'PELEC 001','title': 'Professional Elective 1',          'units': 3, 'year_level': 2, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'professional_elective', 'track': ''},
    {'code': 'CIT 202',  'title': 'Web Systems and Technologies',     'units': 3, 'year_level': 2, 'semester': '1st', 'prerequisite_codes': 'CITE 003,CITE 012', 'subject_type': 'core', 'track': ''},
    {'code': 'CIT 201',  'title': 'Systems Analysis and Design',      'units': 3, 'year_level': 2, 'semester': '1st', 'prerequisite_codes': 'CITE 003,CITE 012', 'subject_type': 'core', 'track': ''},
    {'code': 'BIO 001A', 'title': 'Modern Biology',                   'units': 3, 'year_level': 2, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'core', 'track': ''},
    {'code': 'GEC 008',  'title': 'Ethics',                           'units': 3, 'year_level': 2, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'GEC 007',  'title': 'Science, Technology and Society',  'units': 3, 'year_level': 2, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'PE 201',   'title': 'Physical Education 3',             'units': 2, 'year_level': 2, 'semester': '1st', 'prerequisite_codes': 'PE 102', 'subject_type': 'pe', 'track': ''},

    # ── Second Year, Second Semester
    {'code': 'GEM 001',  'title': 'Life and Works of Rizal',          'units': 3, 'year_level': 2, 'semester': '2nd', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'GEC 003',  'title': 'The Contemporary World',           'units': 3, 'year_level': 2, 'semester': '2nd', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'MATH 028', 'title': 'Applied Statistics',               'units': 3, 'year_level': 2, 'semester': '2nd', 'prerequisite_codes': 'MATH 022', 'subject_type': 'core', 'track': ''},
    {'code': 'CITE 005A','title': 'Information Management',           'units': 3, 'year_level': 2, 'semester': '2nd', 'prerequisite_codes': 'CITE 003,CITE 004', 'subject_type': 'core', 'track': ''},
    {'code': 'PELEC 002','title': 'Professional Elective 2',          'units': 3, 'year_level': 2, 'semester': '2nd', 'prerequisite_codes': '', 'subject_type': 'professional_elective', 'track': ''},
    {'code': 'CIT 203',  'title': 'Platform Technologies',            'units': 3, 'year_level': 2, 'semester': '2nd', 'prerequisite_codes': 'CITE 004', 'subject_type': 'core', 'track': ''},
    {'code': 'CHM 001A', 'title': 'Chemistry',                        'units': 3, 'year_level': 2, 'semester': '2nd', 'prerequisite_codes': '', 'subject_type': 'core', 'track': ''},
    {'code': 'PE 202',   'title': 'Physical Education 4',             'units': 2, 'year_level': 2, 'semester': '2nd', 'prerequisite_codes': 'PE 201', 'subject_type': 'pe', 'track': ''},

    # ── Third Year, First Semester
    {'code': 'GEE 001B', 'title': 'GE Elective 1 – Gender and Society', 'units': 3, 'year_level': 3, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'ITELEC 001','title': 'IT Elective 1',                   'units': 3, 'year_level': 3, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'it_elective', 'track': ''},
    {'code': 'CIT 301',  'title': 'Integrative Programming and Technologies', 'units': 3, 'year_level': 3, 'semester': '1st', 'prerequisite_codes': 'CIT 202,CITE 005A', 'subject_type': 'core', 'track': ''},
    {'code': 'CIT 1302', 'title': 'Quantitative Methods (incl. Modeling and Simulation)', 'units': 3, 'year_level': 3, 'semester': '1st', 'prerequisite_codes': 'MATH 025,MATH 028', 'subject_type': 'core', 'track': ''},
    {'code': 'CIT 303',  'title': 'Networking 1',                     'units': 3, 'year_level': 3, 'semester': '1st', 'prerequisite_codes': 'CIT 202,CIT 203', 'subject_type': 'core', 'track': ''},
    {'code': 'CIT 304',  'title': 'Advanced Database Systems',        'units': 3, 'year_level': 3, 'semester': '1st', 'prerequisite_codes': 'CITE 005A', 'subject_type': 'core', 'track': ''},
    {'code': 'CIT 009',  'title': 'Technopreneurship',                'units': 3, 'year_level': 3, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'core', 'track': ''},
    {'code': 'CITE 305', 'title': 'Systems Integration and Architecture 1', 'units': 3, 'year_level': 3, 'semester': '1st', 'prerequisite_codes': 'CIT 202,CIT 303', 'subject_type': 'core', 'track': ''},

    # ── Third Year, Second Semester
    {'code': 'GEE 002B', 'title': 'GE Elective 2 – Living in the IT Era', 'units': 3, 'year_level': 3, 'semester': '2nd', 'prerequisite_codes': 'GEE 001B', 'subject_type': 'ge', 'track': ''},
    {'code': 'CIS 202',  'title': 'Data Mining and Warehousing',      'units': 3, 'year_level': 3, 'semester': '2nd', 'prerequisite_codes': 'MATH 028,CIT 304', 'subject_type': 'core', 'track': ''},
    {'code': 'CIT 1306', 'title': 'Mobile Computing',                 'units': 3, 'year_level': 3, 'semester': '2nd', 'prerequisite_codes': 'CITE 003,CIT 304', 'subject_type': 'core', 'track': ''},
    {'code': 'PELEC 003','title': 'Professional Elective 3',          'units': 3, 'year_level': 3, 'semester': '2nd', 'prerequisite_codes': '', 'subject_type': 'professional_elective', 'track': ''},
    {'code': 'ITELEC 002','title': 'IT Elective 2',                   'units': 3, 'year_level': 3, 'semester': '2nd', 'prerequisite_codes': 'ITELEC 001', 'subject_type': 'it_elective', 'track': ''},
    {'code': 'CITE 007A','title': 'Information Assurance and Security 1', 'units': 3, 'year_level': 3, 'semester': '2nd', 'prerequisite_codes': 'CIT 304', 'subject_type': 'core', 'track': ''},
    {'code': 'CITE 006', 'title': 'Application Development and Emerging Technologies', 'units': 3, 'year_level': 3, 'semester': '2nd', 'prerequisite_codes': 'CITE 005A', 'subject_type': 'core', 'track': ''},
    {'code': 'CIT 307',  'title': 'Networking 2',                     'units': 3, 'year_level': 3, 'semester': '2nd', 'prerequisite_codes': 'CIT 303', 'subject_type': 'core', 'track': ''},

    # ── Third Year, Summer
    {'code': 'CIT 308',  'title': 'Capstone 1',                       'units': 3, 'year_level': 3, 'semester': 'Summer', 'prerequisite_codes': 'CITE 006,CITE 007A', 'subject_type': 'core', 'track': ''},
    {'code': 'CIT 309',  'title': 'IT Project Management',            'units': 3, 'year_level': 3, 'semester': 'Summer', 'prerequisite_codes': 'CITE 006', 'subject_type': 'core', 'track': ''},
    {'code': 'CIT 310',  'title': 'Information Assurance and Security 2', 'units': 3, 'year_level': 3, 'semester': 'Summer', 'prerequisite_codes': 'CITE 007A', 'subject_type': 'core', 'track': ''},

    # ── Fourth Year, First Semester
    {'code': 'GEE 004',  'title': 'GE Elective 3 – Great Books',      'units': 3, 'year_level': 4, 'semester': '1st', 'prerequisite_codes': 'GEE 002B', 'subject_type': 'ge', 'track': ''},
    {'code': 'PELEC 004','title': 'Professional Elective 4',          'units': 3, 'year_level': 4, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'professional_elective', 'track': ''},
    {'code': 'ITELEC 003','title': 'IT Elective 3',                   'units': 3, 'year_level': 4, 'semester': '1st', 'prerequisite_codes': 'ITELEC 002', 'subject_type': 'it_elective', 'track': ''},
    {'code': 'CIT 400',  'title': 'Capstone 2',                       'units': 3, 'year_level': 4, 'semester': '1st', 'prerequisite_codes': 'CIT 308', 'subject_type': 'core', 'track': ''},
    {'code': 'CITE 008', 'title': 'Social Issues and Professional Practice', 'units': 3, 'year_level': 4, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'core', 'track': ''},
    {'code': 'CIT 401',  'title': 'Systems Administration and Maintenance', 'units': 3, 'year_level': 4, 'semester': '1st', 'prerequisite_codes': 'CIT 310', 'subject_type': 'core', 'track': ''},

    # ── Fourth Year, Second Semester
    {'code': 'CIT 402',  'title': 'Internship in Computing',          'units': 6, 'year_level': 4, 'semester': '2nd', 'prerequisite_codes': '', 'subject_type': 'core', 'track': ''},
    {'code': 'ITELEC 004','title': 'IT Elective 4',                   'units': 3, 'year_level': 4, 'semester': '2nd', 'prerequisite_codes': 'ITELEC 003', 'subject_type': 'it_elective', 'track': ''},
    {'code': 'CIT 403',  'title': 'Systems Integration and Architecture 2', 'units': 3, 'year_level': 4, 'semester': '2nd', 'prerequisite_codes': 'CIT 307,CITE 305,CIT 401', 'subject_type': 'core', 'track': ''},
]

BSCS_SUBJECTS = [
    # ── First Year, First Semester
    {'code': 'GEC 1002', 'title': 'Readings in Philippine History', 'units': 3, 'year_level': 1, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'GEC 004',  'title': 'Mathematics in the Modern World',  'units': 3, 'year_level': 1, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'CS 101',   'title': 'Introduction to Computer Science',   'units': 3, 'year_level': 1, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'core', 'track': ''},
    {'code': 'CS 102',   'title': 'Computer Programming 1 (CS)',      'units': 3, 'year_level': 1, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'core', 'track': ''},
    {'code': 'MATH 022', 'title': 'Linear Algebra (CS)',              'units': 3, 'year_level': 1, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'core', 'track': ''},
    {'code': 'PE 101',   'title': 'Physical Education 1',              'units': 2, 'year_level': 1, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'pe', 'track': ''},
    {'code': 'NSTP 001', 'title': 'National Service Training Program 1','units': 3, 'year_level': 1, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'nstp', 'track': ''},

    # ── First Year, Second Semester
    {'code': 'GEC 001',  'title': 'Understanding the Self',           'units': 3, 'year_level': 1, 'semester': '2nd', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'GEC 005',  'title': 'Purposive Communication',          'units': 3, 'year_level': 1, 'semester': '2nd', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'GEC 006',  'title': 'Art Appreciation',                 'units': 3, 'year_level': 1, 'semester': '2nd', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'CS 103',   'title': 'Computer Programming 2 (CS)',      'units': 3, 'year_level': 1, 'semester': '2nd', 'prerequisite_codes': 'CS 102', 'subject_type': 'core', 'track': ''},
    {'code': 'CS 201',   'title': 'Discrete Structures 1',            'units': 3, 'year_level': 1, 'semester': '2nd', 'prerequisite_codes': 'GEC 004', 'subject_type': 'core', 'track': ''},
    {'code': 'PE 102',   'title': 'Physical Education 2',             'units': 2, 'year_level': 1, 'semester': '2nd', 'prerequisite_codes': 'PE 101', 'subject_type': 'pe', 'track': ''},
    {'code': 'NSTP 002', 'title': 'National Service Training Program 2', 'units': 3, 'year_level': 1, 'semester': '2nd', 'prerequisite_codes': 'NSTP 001', 'subject_type': 'nstp', 'track': ''},

    # ── Second Year, First Semester
    {'code': 'CS 202',   'title': 'Data Structures and Algorithms (CS)', 'units': 3, 'year_level': 2, 'semester': '1st', 'prerequisite_codes': 'CS 103', 'subject_type': 'core', 'track': ''},
    {'code': 'CS 203',   'title': 'Logic Design and Digital Computer Circuits', 'units': 3, 'year_level': 2, 'semester': '1st', 'prerequisite_codes': 'CS 101', 'subject_type': 'core', 'track': ''},
    {'code': 'MATH 030', 'title': 'Calculus 1',                       'units': 3, 'year_level': 2, 'semester': '1st', 'prerequisite_codes': 'MATH 022', 'subject_type': 'core', 'track': ''},
    {'code': 'GEC 008',  'title': 'Ethics',                           'units': 3, 'year_level': 2, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'GEC 007',  'title': 'Science, Technology and Society',  'units': 3, 'year_level': 2, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'BIO 001A', 'title': 'Modern Biology',                   'units': 3, 'year_level': 2, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'core', 'track': ''},
    {'code': 'PE 201',   'title': 'Physical Education 3',             'units': 2, 'year_level': 2, 'semester': '1st', 'prerequisite_codes': 'PE 102', 'subject_type': 'pe', 'track': ''},

    # ── Second Year, Second Semester
    {'code': 'CS 301',   'title': 'Design and Analysis of Algorithms', 'units': 3, 'year_level': 2, 'semester': '2nd', 'prerequisite_codes': 'CS 202,CS 201', 'subject_type': 'core', 'track': ''},
    {'code': 'CS 302',   'title': 'Computer Architecture and Organization', 'units': 3, 'year_level': 2, 'semester': '2nd', 'prerequisite_codes': 'CS 203', 'subject_type': 'core', 'track': ''},
    {'code': 'CS 204',   'title': 'Database Systems (CS)',            'units': 3, 'year_level': 2, 'semester': '2nd', 'prerequisite_codes': 'CS 202', 'subject_type': 'core', 'track': ''},
    {'code': 'MATH 031', 'title': 'Calculus 2',                       'units': 3, 'year_level': 2, 'semester': '2nd', 'prerequisite_codes': 'MATH 030', 'subject_type': 'core', 'track': ''},
    {'code': 'GEM 001',  'title': 'Life and Works of Rizal',          'units': 3, 'year_level': 2, 'semester': '2nd', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'GEC 003',  'title': 'The Contemporary World',           'units': 3, 'year_level': 2, 'semester': '2nd', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'CHM 001A', 'title': 'Chemistry',                        'units': 3, 'year_level': 2, 'semester': '2nd', 'prerequisite_codes': '', 'subject_type': 'core', 'track': ''},
    {'code': 'PE 202',   'title': 'Physical Education 4',             'units': 2, 'year_level': 2, 'semester': '2nd', 'prerequisite_codes': 'PE 201', 'subject_type': 'pe', 'track': ''},

    # ── Third Year, First Semester
    {'code': 'CS 303',   'title': 'Operating Systems',                'units': 3, 'year_level': 3, 'semester': '1st', 'prerequisite_codes': 'CS 302', 'subject_type': 'core', 'track': ''},
    {'code': 'CS 304',   'title': 'Theory of Computation',            'units': 3, 'year_level': 3, 'semester': '1st', 'prerequisite_codes': 'CS 201', 'subject_type': 'core', 'track': ''},
    {'code': 'CS 305',   'title': 'Programming Languages',            'units': 3, 'year_level': 3, 'semester': '1st', 'prerequisite_codes': 'CS 202', 'subject_type': 'core', 'track': ''},
    {'code': 'GEE 001B', 'title': 'GE Elective 1 – Gender and Society', 'units': 3, 'year_level': 3, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'ge', 'track': ''},
    {'code': 'CSELEC 001','title': 'CS Elective 1',                  'units': 3, 'year_level': 3, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'core', 'track': ''},
    {'code': 'CIT 009',  'title': 'Technopreneurship',                'units': 3, 'year_level': 3, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'core', 'track': ''},

    # ── Third Year, Second Semester
    {'code': 'CS 401',   'title': 'Software Engineering 1',           'units': 3, 'year_level': 3, 'semester': '2nd', 'prerequisite_codes': 'CS 202', 'subject_type': 'core', 'track': ''},
    {'code': 'CS 402',   'title': 'Networks and Communications',      'units': 3, 'year_level': 3, 'semester': '2nd', 'prerequisite_codes': 'CS 303', 'subject_type': 'core', 'track': ''},
    {'code': 'CS 403',   'title': 'CS Thesis 1',                      'units': 3, 'year_level': 3, 'semester': '2nd', 'prerequisite_codes': 'CS 301', 'subject_type': 'core', 'track': ''},
    {'code': 'GEE 002B', 'title': 'GE Elective 2 – Living in the IT Era', 'units': 3, 'year_level': 3, 'semester': '2nd', 'prerequisite_codes': 'GEE 001B', 'subject_type': 'ge', 'track': ''},
    {'code': 'CSELEC 002','title': 'CS Elective 2',                  'units': 3, 'year_level': 3, 'semester': '2nd', 'prerequisite_codes': 'CSELEC 001', 'subject_type': 'core', 'track': ''},

    # ── Fourth Year, First Semester
    {'code': 'CS 404',   'title': 'Software Engineering 2',           'units': 3, 'year_level': 4, 'semester': '1st', 'prerequisite_codes': 'CS 401', 'subject_type': 'core', 'track': ''},
    {'code': 'CS 405',   'title': 'CS Thesis 2',                      'units': 3, 'year_level': 4, 'semester': '1st', 'prerequisite_codes': 'CS 403', 'subject_type': 'core', 'track': ''},
    {'code': 'CS 406',   'title': 'Social and Professional Issues (CS)', 'units': 3, 'year_level': 4, 'semester': '1st', 'prerequisite_codes': '', 'subject_type': 'core', 'track': ''},
    {'code': 'GEE 004',  'title': 'GE Elective 3 – Great Books',      'units': 3, 'year_level': 4, 'semester': '1st', 'prerequisite_codes': 'GEE 002B', 'subject_type': 'ge', 'track': ''},
    {'code': 'CSELEC 003','title': 'CS Elective 3',                  'units': 3, 'year_level': 4, 'semester': '1st', 'prerequisite_codes': 'CSELEC 002', 'subject_type': 'core', 'track': ''},

    # ── Fourth Year, Second Semester
    {'code': 'CS 407',   'title': 'CS Practicum',                     'units': 6, 'year_level': 4, 'semester': '2nd', 'prerequisite_codes': '', 'subject_type': 'core', 'track': ''},
    {'code': 'CSELEC 004','title': 'CS Elective 4',                  'units': 3, 'year_level': 4, 'semester': '2nd', 'prerequisite_codes': 'CSELEC 003', 'subject_type': 'core', 'track': ''},
]

class Command(BaseCommand):
    help = 'Seeds the database with the BSIT and BSCS curriculum subjects'

    def handle(self, *args, **options):
        # Program configurations
        configs = [
            ('BSIT', BSIT_SUBJECTS),
            ('BSCS', BSCS_SUBJECTS),
        ]

        total_created = 0
        total_updated = 0

        for program_code, subjects in configs:
            self.stdout.write(f"Seeding {program_code} curriculum...")
            prog_created = 0
            prog_updated = 0
            
            for subj_data in subjects:
                obj, was_created = CurriculumSubject.objects.update_or_create(
                    code=subj_data['code'],
                    program=program_code,
                    defaults={
                        'title': subj_data['title'],
                        'units': subj_data['units'],
                        'year_level': subj_data['year_level'],
                        'semester': subj_data['semester'],
                        'prerequisite_codes': subj_data['prerequisite_codes'],
                        'subject_type': subj_data['subject_type'],
                        'track': subj_data['track'],
                    }
                )
                if was_created:
                    prog_created += 1
                else:
                    prog_updated += 1
            
            self.stdout.write(self.style.SUCCESS(
                f'  {program_code}: {prog_created} created, {prog_updated} updated.'
            ))
            total_created += prog_created
            total_updated += prog_updated

        self.stdout.write(self.style.SUCCESS(
            f'\nTotal curriculum seeding completed: {total_created} created, {total_updated} updated.'
        ))
